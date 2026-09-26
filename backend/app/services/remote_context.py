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
