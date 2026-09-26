from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.deps.auth import require_permission
from app.db.mongo import get_database
from app.services.fundamentals import get_fundamental_snapshot, parse_fundamentals_csv, upsert_fundamentals

router = APIRouter(prefix="/api/v1/fundamentals", tags=["fundamentals"])


@router.get("/{symbol}")
async def fundamental_snapshot(
    symbol: str,
    _: dict = Depends(require_permission("market.read")),
):
    snapshot = await get_fundamental_snapshot(symbol)
    if not snapshot:
        return {"symbol": symbol.upper(), "status": "missing", "fundamentals": None}
    return {"symbol": symbol.upper(), "status": "available", "fundamentals": snapshot}


@router.post("/ingest", status_code=201)
async def ingest_fundamentals(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_permission("admin.data.manage")),
):
    payload = await file.read()
    if not payload:
        raise HTTPException(400, "Uploaded fundamentals file is empty")
    rows = parse_fundamentals_csv(payload)
    if not rows:
        raise HTTPException(400, "No valid fundamentals rows were found")
    ingestion_id = str(uuid4())
    count = await upsert_fundamentals(rows, source="admin-upload", ingestion_id=ingestion_id)
    await get_database().ingestion_runs.insert_one({
        "ingestion_id": ingestion_id,
        "dataset": "fundamental_data",
        "source": "admin-upload",
        "filename": file.filename,
        "records_seen": count,
        "status": "complete",
        "fetched_at": datetime.now(timezone.utc),
        "triggered_by": current_user["user_id"],
    })
    return {"ingestion_id": ingestion_id, "dataset": "fundamental_data", "records_seen": count, "status": "complete"}
