from __future__ import annotations

from uuid import uuid4
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from app.api.deps.auth import require_permission
from app.api.deps.rate_limit import rate_limit
from app.core.config import settings
from app.db.mongo import get_database
from app.services.market_data import build_ingestion_document, parse_exchange_eod

router = APIRouter(prefix="/api/v1/market", tags=["market"])

def _pct(close, previous_close):
    if close is None or previous_close in (None, 0): return None
    return (close - previous_close) / previous_close * 100

async def _latest_trade_date(db, exchange):
    row=await db.eod_market_data.find_one({"exchange":exchange},{"_id":0,"trade_date":1},sort=[("trade_date",-1)])
    return row.get("trade_date") if row else None

async def _read_limited_upload(file: UploadFile) -> bytes:
    data = await file.read(settings.ingestion_max_bytes + 1)
    if len(data) > settings.ingestion_max_bytes:
        raise HTTPException(
            413,
            f"Uploaded EOD file exceeds INGESTION_MAX_BYTES ({settings.ingestion_max_bytes} bytes)",
        )
    return data


@router.post("/eod/ingest", dependencies=[rate_limit("market.eod_ingest", 3, 300)])
async def ingest_eod(exchange: str, file: UploadFile = File(...), current_user: dict = Depends(require_permission("admin.data.manage"))):
    exchange=exchange.upper()
    if exchange not in {"NSE","BSE"}: raise HTTPException(400,"exchange must be NSE or BSE")
    data=await _read_limited_upload(file)
    if not data: raise HTTPException(400,"Uploaded EOD file is empty")
    try: records=parse_exchange_eod(data,exchange,file.filename or "eod.csv")
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc
    if not records: raise HTTPException(400,"No valid EOD rows were found")
    document=build_ingestion_document(records,source=exchange)
    trade_date=document["trade_date"]; ingestion_id=str(uuid4())
    normalized=[]
    for record in records:
        item=record.model_dump()
        item.update({"ingestion_id":ingestion_id,"ingested_at":document["fetched_at"],"source":"exchange","source_dataset":document["source"]})
        normalized.append(item)
    db=get_database()
    await db.eod_market_data.delete_many({"exchange":exchange,"trade_date":trade_date})
    await db.eod_market_data.insert_many(normalized,ordered=False)
    await db.ingestion_runs.insert_one({"ingestion_id":ingestion_id,"dataset":"eod_market_data","exchange":exchange,"trade_date":trade_date,"source":document["source"],"filename":file.filename,"records_seen":document["records_seen"],"records_missing_core_prices":document["records_missing_core_prices"],"status":document["status"],"fetched_at":document["fetched_at"],"triggered_by":current_user["user_id"]})
    return {"ingestion_id":ingestion_id,"exchange":exchange,"trade_date":trade_date,"records_seen":document["records_seen"],"records_missing_core_prices":document["records_missing_core_prices"],"status":document["status"]}

@router.get("/eod/status")
async def eod_status(exchange: str | None = Query(default=None), _: dict = Depends(require_permission("market.read"))):
    db=get_database(); filters={"exchange":exchange.upper()} if exchange else {}
    latest=await db.ingestion_runs.find_one(filters,{"_id":0},sort=[("trade_date",-1),("fetched_at",-1)])
    if not latest: return {"status":"unavailable","exchange":exchange.upper() if exchange else None}
    return {"status":latest.get("status"),"exchange":latest.get("exchange"),"trade_date":latest.get("trade_date"),"records_seen":latest.get("records_seen",0),"records_missing_core_prices":latest.get("records_missing_core_prices",0),"source":latest.get("source"),"fetched_at":latest.get("fetched_at")}

@router.get("/eod/overview")
async def eod_overview(_: dict = Depends(require_permission("market.read"))):
    db=get_database(); exchanges=[]
    for exchange in ("NSE","BSE"):
        trade_date=await _latest_trade_date(db,exchange)
        if not trade_date:
            exchanges.append({"exchange":exchange,"data_status":"missing","trade_date":None,"records":0,"positive":0,"negative":0,"unchanged":0,"breadth_pct":None,"top_gainers":[],"top_losers":[]})
            continue
        docs=await db.eod_market_data.find({"exchange":exchange,"trade_date":trade_date},{"_id":0,"symbol":1,"name":1,"close":1,"previous_close":1,"volume":1}).to_list(length=10000)
        movers=[]; positive=negative=unchanged=0
        for row in docs:
            change=_pct(row.get("close"),row.get("previous_close"))
            if change is None: continue
            if change>0: positive+=1
            elif change<0: negative+=1
            else: unchanged+=1
            movers.append({"symbol":row.get("symbol"),"name":row.get("name"),"close":row.get("close"),"change_pct":change,"volume":row.get("volume"),"data_status":"eod","trade_date":trade_date})
        usable=positive+negative+unchanged
        breadth=((positive-negative)/usable*100) if usable else None
        movers.sort(key=lambda x:x["change_pct"],reverse=True)
        run=await db.ingestion_runs.find_one({"exchange":exchange,"trade_date":trade_date},{"_id":0,"fetched_at":1,"source":1,"status":1},sort=[("fetched_at",-1)])
        exchanges.append({"exchange":exchange,"data_status":"eod","trade_date":trade_date,"records":len(docs),"positive":positive,"negative":negative,"unchanged":unchanged,"breadth_pct":breadth,"top_gainers":movers[:10],"top_losers":sorted(movers,key=lambda x:x["change_pct"])[:10],"source":run.get("source") if run else "exchange","fetched_at":run.get("fetched_at") if run else None,"ingestion_status":run.get("status") if run else "unknown"})
    return {"exchanges":exchanges}

@router.get("/eod/history")
async def eod_history(symbol: str = Query(min_length=1,max_length=32), exchange: str = Query(default="NSE",pattern="^(?i:NSE|BSE)$"), sessions: int = Query(default=6,ge=1,le=30), _: dict = Depends(require_permission("market.read"))):
    exchange=exchange.upper(); db=get_database()
    docs=await db.eod_market_data.find({"exchange":exchange,"symbol":symbol.upper()},{"_id":0}).sort("trade_date",-1).to_list(length=sessions)
    docs.reverse()
    for row in docs:
        row["change_pct"]=_pct(row.get("close"),row.get("previous_close")); row["data_status"]="eod"
    return {"exchange":exchange,"symbol":symbol.upper(),"sessions":docs,"count":len(docs)}


@router.get("/status")
async def market_status():
    from datetime import datetime, time
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    open_time = time(9, 15)
    close_time = time(15, 30)
    weekday = now.weekday() < 5
    db = get_database()
    holiday = await db.exchange_holidays.find_one({"exchange": "NSE", "date": now.date().isoformat()}, {"_id": 0, "description": 1})
    calendar_available = await db.exchange_holidays.find_one({"exchange": "NSE"}, {"_id": 0, "date": 1}) is not None
    in_session = weekday and not holiday and open_time <= now.time() < close_time
    return {
        "timestamp": now.isoformat(),
        "timezone": "Asia/Kolkata",
        "nse": {"status": "open" if in_session else "closed", "normal_session": "09:15-15:30"},
        "bse": {"status": "open" if in_session else "closed", "normal_session": "09:15-15:30"},
        "calendar_basis": "NSE holiday calendar" if calendar_available else "weekday schedule only; exchange holiday calendar is not loaded",
        "holiday": holiday,
        "data_layers": {
            "live": "websocket",
            "eod": "scheduled after market close",
        },
    }


@router.get("/index/overview")
async def index_overview(_: dict = Depends(require_permission("market.read"))):
    db = get_database()
    rows = []
    for exchange in ("NSE", "BSE"):
        latest = await db.index_data.find_one(
            {"exchange": exchange},
            {"_id": 0},
            sort=[("trade_date", -1)],
        )
        rows.append({
            "exchange": exchange,
            "data_status": "eod" if latest else "missing",
            "symbol": latest.get("symbol") if latest else None,
            "trade_date": latest.get("trade_date") if latest else None,
            "close": latest.get("close") if latest else None,
            "previous_close": latest.get("previous_close") if latest else None,
            "change_pct": (
                _pct(latest.get("close"), latest.get("previous_close"))
                if latest else None
            ),
            "source_url": latest.get("source_url") if latest else None,
        })
    return {"indices": rows}
