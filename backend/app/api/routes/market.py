from fastapi import APIRouter, File, HTTPException, UploadFile
from app.db.mongo import get_database
from app.services.market_data import build_ingestion_document, parse_exchange_eod

router = APIRouter(prefix="/api/v1/market", tags=["market"])

@router.post("/eod/ingest")
async def ingest_eod(exchange: str, file: UploadFile = File(...)):
    exchange = exchange.upper()
    if exchange not in {"NSE", "BSE"}:
        raise HTTPException(400, "exchange must be NSE or BSE")

    data = await file.read()
    try:
        records = parse_exchange_eod(data, exchange, file.filename or "eod.csv")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    document = build_ingestion_document(records, source=exchange)
    db = get_database()
    await db.eod_market_data.insert_one(document)
    await db.ingestion_runs.insert_one({
        "dataset": "eod_market_data",
        "exchange": exchange,
        "trade_date": document["trade_date"],
        "source": document["source"],
        "records_seen": document["records_seen"],
        "status": document["status"],
        "fetched_at": document["fetched_at"],
    })
    return {
        "exchange": exchange,
        "trade_date": document["trade_date"],
        "records_seen": document["records_seen"],
        "records_missing_core_prices": document["records_missing_core_prices"],
        "status": document["status"],
    }

@router.get("/eod/status")
async def eod_status():
    db = get_database()
    latest = await db.eod_market_data.find_one(sort=[("trade_date", -1), ("fetched_at", -1)])
    if not latest:
        return {"status": "unavailable"}
    return {
        "status": latest.get("status"),
        "exchange": latest.get("exchange"),
        "trade_date": latest.get("trade_date"),
        "records_seen": latest.get("records_seen", 0),
        "records_missing_core_prices": latest.get("records_missing_core_prices", 0),
        "source": latest.get("source"),
    }
