from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps.auth import require_permission
from app.db.mongo import get_database

router = APIRouter(prefix="/api/v1/exchanges", tags=["exchanges"])


def _pct(close, previous_close):
    if close is None or previous_close in (None, 0):
        return None
    return (close - previous_close) / previous_close * 100


async def _exchange_snapshot(db, exchange: str):
    latest = await db.eod_market_data.find_one(
        {"exchange": exchange},
        {"_id": 0, "trade_date": 1},
        sort=[("trade_date", -1)],
    )
    if not latest:
        return {
            "exchange": exchange,
            "data_status": "missing",
            "trade_date": None,
            "records": 0,
            "positive": 0,
            "negative": 0,
            "unchanged": 0,
            "breadth_pct": None,
            "average_change_pct": None,
            "total_volume": None,
            "total_turnover": None,
            "top_gainers": [],
            "top_losers": [],
            "source": None,
            "fetched_at": None,
        }

    trade_date = latest["trade_date"]
    docs = await db.eod_market_data.find(
        {"exchange": exchange, "trade_date": trade_date},
        {"_id": 0, "symbol": 1, "name": 1, "close": 1, "previous_close": 1, "volume": 1, "turnover": 1},
    ).to_list(length=10000)

    movers = []
    positive = negative = unchanged = 0
    total_volume = total_turnover = 0.0
    has_volume = has_turnover = False

    for row in docs:
        change = _pct(row.get("close"), row.get("previous_close"))
        if change is None:
            continue
        if change > 0:
            positive += 1
        elif change < 0:
            negative += 1
        else:
            unchanged += 1
        if row.get("volume") is not None:
            total_volume += row["volume"]
            has_volume = True
        if row.get("turnover") is not None:
            total_turnover += row["turnover"]
            has_turnover = True
        movers.append({
            "symbol": row.get("symbol"),
            "name": row.get("name"),
            "close": row.get("close"),
            "change_pct": change,
            "volume": row.get("volume"),
        })

    usable = positive + negative + unchanged
    breadth = ((positive - negative) / usable * 100) if usable else None
    average = sum(item["change_pct"] for item in movers) / len(movers) if movers else None
    gainers = sorted(movers, key=lambda x: x["change_pct"], reverse=True)[:10]
    losers = sorted(movers, key=lambda x: x["change_pct"])[:10]

    run = await db.ingestion_runs.find_one(
        {"exchange": exchange, "trade_date": trade_date},
        {"_id": 0, "source": 1, "fetched_at": 1, "status": 1},
        sort=[("fetched_at", -1)],
    )

    return {
        "exchange": exchange,
        "data_status": "eod",
        "trade_date": trade_date,
        "records": len(docs),
        "positive": positive,
        "negative": negative,
        "unchanged": unchanged,
        "breadth_pct": breadth,
        "average_change_pct": average,
        "total_volume": total_volume if has_volume else None,
        "total_turnover": total_turnover if has_turnover else None,
        "top_gainers": gainers,
        "top_losers": losers,
        "source": run.get("source") if run else "exchange",
        "fetched_at": run.get("fetched_at") if run else None,
    }


@router.get("/comparison")
async def exchange_comparison(_: dict = Depends(require_permission("market.read"))):
    db = get_database()
    nse, bse = await _exchange_snapshot(db, "NSE"), await _exchange_snapshot(db, "BSE")

    stock_query = {
        "trade_date": {"$in": [d for d in (nse["trade_date"], bse["trade_date"]) if d]}
    }
    paired = []
    if nse["trade_date"] and bse["trade_date"]:
        nse_rows = await db.eod_market_data.find(
            {"exchange": "NSE", "trade_date": nse["trade_date"]},
            {"_id": 0, "symbol": 1, "close": 1, "previous_close": 1},
        ).to_list(length=10000)
        bse_rows = await db.eod_market_data.find(
            {"exchange": "BSE", "trade_date": bse["trade_date"]},
            {"_id": 0, "symbol": 1, "close": 1, "previous_close": 1},
        ).to_list(length=10000)
        bse_map = {row["symbol"].upper(): row for row in bse_rows if row.get("symbol")}
        for row in nse_rows:
            symbol = (row.get("symbol") or "").upper()
            match = bse_map.get(symbol)
            if not match:
                continue
            nse_change = _pct(row.get("close"), row.get("previous_close"))
            bse_change = _pct(match.get("close"), match.get("previous_close"))
            if nse_change is None or bse_change is None:
                continue
            paired.append({
                "symbol": symbol,
                "nse_change_pct": nse_change,
                "bse_change_pct": bse_change,
                "spread_pct": nse_change - bse_change,
            })
        paired.sort(key=lambda x: abs(x["spread_pct"]), reverse=True)

    index_rows = await db.index_data.find({"trade_date": {"$in": [d for d in (nse["trade_date"], bse["trade_date"]) if d]}}, {"_id": 0, "exchange": 1, "symbol": 1, "trade_date": 1, "close": 1, "previous_close": 1}).sort([("trade_date", -1)]).to_list(length=20)
    index_performance = []
    for row in index_rows:
        index_performance.append({**row, "change_pct": _pct(row.get("close"), row.get("previous_close")), "data_status": "eod"})

    return {
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        "exchanges": {"NSE": nse, "BSE": bse},
        "index_performance": index_performance,
        "index_note": "Index values come only from dedicated index_data ingestion; equity bhavcopy records are not used as a substitute." ,
        "stock_level_comparison": {
            "matched_symbols": len(paired),
            "largest_change_spreads": paired[:20],
        },
        "comparison_fields": [
            "trade_date", "records", "breadth_pct", "average_change_pct",
            "total_volume", "total_turnover",
        ],
    }
