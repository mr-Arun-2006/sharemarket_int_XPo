from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.api.deps.auth import require_permission
from app.db.mongo import get_database
from app.services.context_data import build_market_context, parse_context_csv

router = APIRouter(prefix="/api/v1/market/context", tags=["market-context"])


@router.post("/ingest/{kind}")
async def ingest_context(
    kind: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(require_permission("admin.data.manage")),
):
    if kind not in {"sector", "institutional", "event"}:
        raise HTTPException(400, "kind must be sector, institutional, event or holiday")
    data = await file.read()
    if not data:
        raise HTTPException(400, "Uploaded context file is empty")

    rows = parse_context_csv(data, kind)
    if not rows:
        raise HTTPException(400, f"No valid {kind} rows were found")

    db = get_database()
    now = datetime.now(timezone.utc)
    ingestion_id = str(uuid4())

    if kind == "sector":
        await db.sector_data.delete_many({})
        await db.sector_data.insert_many(
            [{**row, "ingestion_id": ingestion_id, "ingested_at": now} for row in rows],
            ordered=False,
        )
        dataset = "sector_data"
    elif kind == "institutional":
        await db.institutional_activity.insert_many(
            [{**row, "ingestion_id": ingestion_id, "ingested_at": now} for row in rows],
            ordered=False,
        )
        dataset = "institutional_activity"
    else:
        await db.market_events.insert_many(
            [{**row, "ingestion_id": ingestion_id, "ingested_at": now} for row in rows],
            ordered=False,
        )
        dataset = "market_events"

    await db.ingestion_runs.insert_one({
        "ingestion_id": ingestion_id,
        "dataset": dataset,
        "source": "admin-upload",
        "filename": file.filename,
        "records_seen": len(rows),
        "status": "complete",
        "fetched_at": now,
        "triggered_by": current_user["user_id"],
    })
    return {
        "ingestion_id": ingestion_id,
        "dataset": dataset,
        "records_seen": len(rows),
        "status": "complete",
    }


@router.get("/overview")
async def context_overview(
    trade_date: str | None = Query(default=None, max_length=16),
    _: dict = Depends(require_permission("market.read")),
):
    db = get_database()
    if trade_date is None:
        latest = await db.eod_market_data.find_one(
            {"exchange": "NSE"},
            {"_id": 0, "trade_date": 1},
            sort=[("trade_date", -1)],
        )
        trade_date = latest.get("trade_date") if latest else None

    if not trade_date:
        return {"trade_date": None, "status": "missing"}

    context = await build_market_context(trade_date)
    return {
        "trade_date": trade_date,
        "status": "available" if (
            context["sectors"] or context["institutional_activity"] or context["major_events"]
        ) else "missing",
        **context,
    }
