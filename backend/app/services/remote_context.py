from __future__ import annotations

from datetime import date, datetime, timezone

from app.db.mongo import get_database
from app.services.context_data import parse_context_csv
from app.services.remote_ingestion import expand_url, fetch_source


async def ingest_remote_context(kind: str, url_template: str, target_day: date | None = None) -> dict:
    if kind not in {"sector", "institutional", "event"}:
        raise ValueError("Unsupported context kind")
    if not url_template.strip():
        raise ValueError(f"{kind} source URL template is not configured")

    day = target_day or datetime.now(timezone.utc).date()
    url = expand_url(url_template, day)
    payload, metadata = await fetch_source(url)
    rows = parse_context_csv(payload, kind)
    if not rows:
        raise ValueError(f"{kind} source returned no parseable rows")

    db = get_database()
    now = datetime.now(timezone.utc)
    digest = metadata["sha256"]
    dataset = {"sector": "sector_data", "institutional": "institutional_activity", "event": "market_events"}[kind]

    existing = await db.ingestion_runs.find_one(
        {"dataset": dataset, "sha256": digest},
        {"_id": 0, "ingestion_id": 1, "status": 1},
        sort=[("fetched_at", -1)],
    )
    if existing:
        return {
            "dataset": dataset,
            "status": "already_ingested",
            "ingestion_id": existing.get("ingestion_id"),
        }

    ingestion_id = f"{dataset}-{digest[:20]}"

    documents = [
        {
            **row,
            "ingestion_id": ingestion_id,
            "source_url": metadata["url"],
            "source_sha256": digest,
            "ingested_at": now,
        }
        for row in rows
    ]

    if kind == "sector":
        await db.sector_data.delete_many({})
        await db.sector_data.insert_many(documents, ordered=False)
    else:
        await db[dataset].insert_many(documents, ordered=False)

    await db.ingestion_runs.insert_one({
        "ingestion_id": ingestion_id,
        "dataset": dataset,
        "source": metadata["url"],
        "sha256": digest,
        "bytes": metadata["bytes"],
        "records_seen": len(rows),
        "status": "complete",
        "fetched_at": now,
    })

    return {
        "dataset": dataset,
        "status": "complete",
        "ingestion_id": ingestion_id,
        "records_seen": len(rows),
        "source_url": metadata["url"],
    }

async def ingest_nse_institutional(target_day: date | None = None) -> dict:
    """Fetch the official NSE FII/FPI + DII JSON endpoint using a primed web session."""
    day = target_day or datetime.now(timezone.utc).date()
    import hashlib
    import httpx

    url = "https://www.nseindia.com/api/fiidiiTradeReact"
    headers = {
        "User-Agent": "ShareM-Int-Xpo/1.0 (+market-data-ingestion)",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://www.nseindia.com/reports/fii-dii",
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=45.0, headers=headers) as client:
        landing = await client.get("https://www.nseindia.com/")
        landing.raise_for_status()
        response = await client.get(url)
        response.raise_for_status()
        payload = response.json()

    if not isinstance(payload, list):
        raise ValueError("NSE FII/DII endpoint returned an unexpected JSON shape")

    from app.services.context_data import _normalize_date, _float
    parsed = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        trade_date = _normalize_date(raw.get("date") or raw.get("tradeDate") or raw.get("businessDate"))
        category = str(raw.get("category") or raw.get("investorCategory") or "").strip()
        if not trade_date or not category:
            continue
        buy = _float(raw.get("buyValue") if raw.get("buyValue") is not None else raw.get("buy"))
        sell = _float(raw.get("sellValue") if raw.get("sellValue") is not None else raw.get("sell"))
        net = _float(raw.get("netValue") if raw.get("netValue") is not None else raw.get("net"))
        if net is None and buy is not None and sell is not None:
            net = buy - sell
        parsed.append({
            "trade_date": trade_date,
            "category": category,
            "buy_value": buy,
            "sell_value": sell,
            "net_value": net,
            "source": "NSE /api/fiidiiTradeReact",
        })

    target = day.isoformat()
    rows = [row for row in parsed if row["trade_date"] == target]
    if not rows:
        available = sorted({row["trade_date"] for row in parsed}, reverse=True)
        raise ValueError(f"NSE FII/DII data does not contain {target}; latest available={available[:3]}")

    digest = hashlib.sha256(response.content).hexdigest()
    db = get_database()
    now = datetime.now(timezone.utc)
    existing = await db.ingestion_runs.find_one(
        {"dataset": "institutional_activity", "trade_date": target, "sha256": digest},
        {"_id": 0, "ingestion_id": 1},
    )
    if existing:
        return {"dataset": "institutional_activity", "trade_date": target, "status": "already_ingested", "ingestion_id": existing.get("ingestion_id")}

    ingestion_id = "institutional_activity-" + digest[:20]
    documents = [{**row, "ingestion_id": ingestion_id, "source_url": url, "source_sha256": digest, "ingested_at": now} for row in rows]
    await db.institutional_activity.delete_many({"trade_date": target})
    await db.institutional_activity.insert_many(documents, ordered=False)
    await db.ingestion_runs.insert_one({
        "ingestion_id": ingestion_id,
        "dataset": "institutional_activity",
        "trade_date": target,
        "source": url,
        "sha256": digest,
        "bytes": len(response.content),
        "records_seen": len(rows),
        "status": "complete",
        "fetched_at": now,
    })
    return {"dataset": "institutional_activity", "trade_date": target, "status": "complete", "ingestion_id": ingestion_id, "records_seen": len(rows), "source_url": url}