from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from app.db.mongo import get_database
from app.schemas.market import EODRecord
from app.services.technical import compute_technical_snapshot

router = APIRouter(prefix="/api/v1/stocks", tags=["stocks"])

def _pct(close: float | None, previous_close: float | None) -> float | None:
    if close is None or previous_close in (None, 0): return None
    return (close - previous_close) / previous_close * 100

@router.get("")
async def list_stocks(exchange: str = Query(default="NSE", pattern="^(?i:NSE|BSE)$"), q: str = Query(default="", max_length=64), limit: int = Query(default=50, ge=1, le=200)):
    exchange = exchange.upper(); db = get_database()
    latest = await db.eod_market_data.find_one({"exchange": exchange}, {"_id": 0, "trade_date": 1}, sort=[("trade_date", -1)])
    if not latest: return {"exchange": exchange, "trade_date": None, "stocks": []}
    query = {"exchange": exchange, "trade_date": latest["trade_date"]}
    if q.strip():
        term = q.strip()
        query["$or"] = [{"symbol": {"$regex": term, "$options": "i"}}, {"name": {"$regex": term, "$options": "i"}}]
    docs = await db.eod_market_data.find(query, {"_id": 0, "symbol": 1, "name": 1, "close": 1, "previous_close": 1, "volume": 1}).sort("symbol", 1).to_list(length=limit)
    return {"exchange": exchange, "trade_date": latest["trade_date"], "stocks": [{**row, "change_pct": _pct(row.get("close"), row.get("previous_close")), "data_status": "eod"} for row in docs]}

@router.get("/{symbol}")
async def get_stock(symbol: str, exchange: str = Query(default="NSE", pattern="^(?i:NSE|BSE)$"), sessions: int = Query(default=60, ge=20, le=252)):
    exchange = exchange.upper(); symbol = symbol.upper(); db = get_database()
    docs = await db.eod_market_data.find({"exchange": exchange, "symbol": symbol}, {"_id": 0}).sort("trade_date", -1).to_list(length=sessions)
    if not docs: raise HTTPException(404, f"No {exchange} EOD data found for {symbol}")
    docs.reverse(); records = []
    for row in docs:
        try: records.append(EODRecord.model_validate(row))
        except Exception: pass
    if not records: raise HTTPException(422, "Stored stock data is invalid")
    technical = compute_technical_snapshot(records); latest = records[-1]
    return {"exchange": exchange, "symbol": symbol, "name": latest.name, "latest": {"trade_date": latest.trade_date, "close": latest.close, "previous_close": latest.previous_close, "change_pct": _pct(latest.close, latest.previous_close), "volume": latest.volume, "turnover": latest.turnover, "trades": latest.trades, "data_status": "eod"}, "technical": technical.__dict__, "history": [{"trade_date": r.trade_date, "open": r.open, "high": r.high, "low": r.low, "close": r.close, "volume": r.volume, "change_pct": _pct(r.close, r.previous_close), "data_status": "eod"} for r in records]}
