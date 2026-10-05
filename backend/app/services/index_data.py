from __future__ import annotations

import csv
import io
import re
import zipfile
import hashlib

from app.services.remote_ingestion import fetch_source, expand_url
from datetime import date, datetime, timezone


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.strip().lower())


ALIASES = {
    "symbol": ("index", "indexname", "symbol", "index_name", "indexname"),
    "trade_date": ("date", "tradedate", "trade_date", "businessdate"),
    "open": ("open", "openindexvalue", "openindex"),
    "high": ("high", "highindexvalue", "highindex"),
    "low": ("low", "lowindexvalue", "lowindex"),
    "close": ("close", "closingindexvalue", "closeindex", "indexvalue", "close"),
    "previous_close": ("previousclose", "prevclose", "previous_close"),
}


def _choose(row: dict[str, str], names: tuple[str, ...]):
    normalized = {_key(k): v for k, v in row.items()}
    for name in names:
        value = normalized.get(_key(name))
        if value not in (None, ""):
            return value
    return None


def _date(value: str | None) -> str | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y", "%d%b%Y", "%Y%m%d"):
        from datetime import datetime
        try:
            return datetime.strptime(value.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _float(value: str | None):
    if value is None:
        return None
    try:
        return float(value.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def parse_index_file(data: bytes) -> list[dict]:
    if data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = [n for n in archive.namelist() if n.lower().endswith((".csv", ".txt"))]
            if not names:
                raise ValueError("Index ZIP contains no CSV/TXT file")
            data = archive.read(max(names, key=lambda n: archive.getinfo(n).file_size))

    text = data.decode("utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",|;	")
    except csv.Error:
        dialect = csv.excel

    rows = []
    for raw in csv.DictReader(io.StringIO(text), dialect=dialect):
        symbol = _choose(raw, ALIASES["symbol"])
        trade_date = _date(_choose(raw, ALIASES["trade_date"]))
        close = _float(_choose(raw, ALIASES["close"]))
        if not symbol or not trade_date or close is None:
            continue
        rows.append({
            "symbol": symbol.strip(),
            "trade_date": trade_date,
            "open": _float(_choose(raw, ALIASES["open"])),
            "high": _float(_choose(raw, ALIASES["high"])),
            "low": _float(_choose(raw, ALIASES["low"])),
            "close": close,
            "previous_close": _float(_choose(raw, ALIASES["previous_close"])),
        })
    return rows


async def ingest_remote_index(url_template: str, exchange: str, target_day: date | None = None) -> dict:
    exchange = exchange.upper()
    if exchange not in {"NSE", "BSE"}:
        raise ValueError("exchange must be NSE or BSE")
    if not url_template.strip():
        raise ValueError(f"{exchange} index source URL template is not configured")

    requested_day = target_day or datetime.now(timezone.utc).date()
    last_error: Exception | None = None
    rows: list[dict] = []
    meta: dict = {}
    trade_date: str | None = None

    for offset in range(8):
        candidate = requested_day.fromordinal(requested_day.toordinal() - offset)
        url = expand_url(url_template, candidate)
        try:
            data, candidate_meta = await fetch_source(url)
            parsed = parse_index_file(data)
            if not parsed:
                raise ValueError("Index source returned no parseable rows")
            unique_dates = {row["trade_date"] for row in parsed}
            if unique_dates != {candidate.isoformat()}:
                raise ValueError(
                    f"Index source date mismatch: expected {candidate.isoformat()}, got {sorted(unique_dates)}"
                )
            rows = parsed
            meta = candidate_meta
            trade_date = candidate.isoformat()
            break
        except Exception as exc:
            last_error = exc

    if not rows or trade_date is None:
        raise ValueError(
            f"{exchange} index source unavailable for recent trading-day window: {last_error}"
        )

    from app.db.mongo import get_database
    db = get_database()
    digest = meta["sha256"]
    existing = await db.index_data.find_one(
        {"exchange": exchange, "trade_date": trade_date, "sha256": digest},
        {"_id": 0, "ingestion_id": 1},
    )
    if existing:
        return {
            "status": "already_ingested",
            "ingestion_id": existing["ingestion_id"],
            "trade_date": trade_date,
        }

    ingestion_id = f"{exchange.lower()}-index-{trade_date}-{digest[:12]}"
    now = datetime.now(timezone.utc)
    docs = [
        {
            **row,
            "exchange": exchange,
            "sha256": digest,
            "ingestion_id": ingestion_id,
            "source_url": meta["url"],
            "ingested_at": now,
        }
        for row in rows
    ]
    await db.index_data.delete_many({"exchange": exchange, "trade_date": trade_date})
    await db.index_data.insert_many(docs, ordered=False)
    await db.ingestion_runs.update_one(
        {
            "dataset": "index_data",
            "exchange": exchange,
            "trade_date": trade_date,
            "sha256": digest,
        },
        {
            "$set": {
                "ingestion_id": ingestion_id,
                "source": meta["url"],
                "sha256": digest,
                "bytes": meta["bytes"],
                "records_seen": len(docs),
                "status": "complete",
                "fetched_at": now,
            }
        },
        upsert=True,
    )
    return {
        "status": "complete",
        "ingestion_id": ingestion_id,
        "exchange": exchange,
        "trade_date": trade_date,
        "records_seen": len(docs),
        "source_url": meta["url"],
        "sha256": digest,
    }
