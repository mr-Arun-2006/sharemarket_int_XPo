from __future__ import annotations

from datetime import date, datetime, timezone
from urllib.parse import urlparse
import hashlib
import re

import httpx

from app.db.mongo import get_database
from app.services.market_data import build_ingestion_document, parse_exchange_eod


def expand_url(template: str, day: date) -> str:
    values = {
        "date": day.strftime("%Y-%m-%d"),
        "ddmmyyyy": day.strftime("%d%m%Y"),
        "ddmmyy": day.strftime("%d%m%y"),
        "yyyymmdd": day.strftime("%Y%m%d"),
    }
    return template.format(**values)


async def fetch_source(url: str, timeout: float = 45.0) -> tuple[bytes, dict]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("EOD source URL must use http or https")

    headers = {
        "User-Agent": "ShareM-Int-Xpo/1.0 (+market-data-ingestion)",
        "Accept": "application/zip, text/csv, application/octet-stream, */*",
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout, headers=headers) as client:
        response = await client.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        return response.content, {
            "url": str(response.url),
            "content_type": content_type,
            "http_status": response.status_code,
            "sha256": hashlib.sha256(response.content).hexdigest(),
            "bytes": len(response.content),
        }


async def ingest_remote_eod(exchange: str, url_template: str, target_day: date | None = None) -> dict:
    exchange = exchange.upper()
    if exchange not in {"NSE", "BSE"}:
        raise ValueError("exchange must be NSE or BSE")
    if not url_template.strip():
        raise ValueError(f"{exchange} EOD source URL template is not configured")

    day = target_day or datetime.now(timezone.utc).date()
    started = datetime.now(timezone.utc)
    last_error = None
    records = []
    source_meta = {}
    url = ""
    attempted_dates = []

    # Exchange source availability can lag calendar dates because of weekends and holidays.
    # Try the requested date and up to seven prior calendar days, accepting only an exact date match.
    for offset in range(8):
        candidate = day.fromordinal(day.toordinal() - offset)
        attempted_dates.append(candidate.isoformat())
        candidate_url = expand_url(url_template, candidate)
        try:
            data, candidate_meta = await fetch_source(candidate_url)
            parsed = parse_exchange_eod(data, exchange, filename=candidate_url.rsplit("/", 1)[-1] or "remote_eod")
            if not parsed:
                raise ValueError(f"{exchange} source returned no parseable EOD rows")
            unique_dates = {r.trade_date for r in parsed}
            if unique_dates != {candidate.isoformat()}:
                raise ValueError(
                    f"{exchange} source date mismatch: expected {candidate.isoformat()}, got {sorted(unique_dates)}"
                )
            records = parsed
            source_meta = candidate_meta
            url = candidate_url
            day = candidate
            break
        except Exception as exc:
            last_error = exc

    if not records:
        raise ValueError(
            f"{exchange} source unavailable for recent trading-day window {attempted_dates}: {last_error}"
        )

    document = build_ingestion_document(records, source=source_meta["url"], fetched_at=started)
    db = get_database()
    trade_date = document["trade_date"]

    # Validate that source data belongs to a single trading date before replacing it.
    unique_dates = {r.trade_date for r in records}
    if len(unique_dates) != 1:
        raise ValueError(f"{exchange} source contains multiple trade dates: {sorted(unique_dates)}")
    if trade_date is None:
        raise ValueError(f"{exchange} source did not provide a trade date")

    digest = source_meta["sha256"]
    existing = await db.ingestion_runs.find_one(
        {"exchange": exchange, "trade_date": trade_date, "sha256": digest},
        {"_id": 0, "ingestion_id": 1, "status": 1},
    )
    if existing:
        return {
            "exchange": exchange,
            "trade_date": trade_date,
            "status": "already_ingested",
            "ingestion_id": existing.get("ingestion_id"),
        }

    ingestion_id = hashlib.sha256(
        f"{exchange}:{trade_date}:{digest}".encode()
    ).hexdigest()[:32]

    normalized = []
    for record in records:
        item = record.model_dump()
        item.update({
            "ingestion_id": ingestion_id,
            "ingested_at": started,
            "source": "exchange",
            "source_dataset": source_meta["url"],
        })
        normalized.append(item)

    await db.eod_market_data.delete_many({"exchange": exchange, "trade_date": trade_date})
    await db.eod_market_data.insert_many(normalized, ordered=False)

    result = {
        "ingestion_id": ingestion_id,
        "dataset": "eod_market_data",
        "exchange": exchange,
        "trade_date": trade_date,
        "source_url": source_meta["url"],
        "filename": url.rsplit("/", 1)[-1] or None,
        "sha256": digest,
        "bytes": source_meta["bytes"],
        "records_seen": document["records_seen"],
        "records_missing_core_prices": document["records_missing_core_prices"],
        "status": document["status"],
        "fetched_at": started,
    }
    await db.ingestion_runs.insert_one(result)
    return result


def validate_index_rows(rows: list[dict]) -> list[dict]:
    valid = []
    for row in rows:
        symbol = row.get("symbol") or row.get("index") or row.get("index_name")
        trade_date = row.get("trade_date") or row.get("date")
        close = row.get("close") or row.get("closing_value") or row.get("closingindexvalue")
        if not symbol or not trade_date or close in (None, ""):
            continue
        valid.append({
            "symbol": str(symbol).strip(),
            "trade_date": str(trade_date).strip(),
            "open": row.get("open"),
            "high": row.get("high"),
            "low": row.get("low"),
            "close": close,
            "previous_close": row.get("previous_close") or row.get("prev_close"),
            "source": row.get("source", "exchange"),
        })
    return valid
