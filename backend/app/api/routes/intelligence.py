from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Query
from app.db.mongo import get_database
from app.services.eod_engine import build_market_summary
from app.schemas.market import EODRecord

router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])

DISCLAIMER = "For informational purposes only. This is not investment advice."

@router.post("/eod")
async def generate_eod_intelligence(symbol: str | None = Query(default=None, max_length=32)):
    db = get_database()
    cursor = db.eod_market_data.find({}, {"records": 1})
    records: list[EODRecord] = []
    async for document in cursor:
        for raw in document.get("records", []):
            try:
                records.append(EODRecord.model_validate(raw))
            except Exception:
                continue
    if not records:
        raise HTTPException(404, "No EOD dataset is available")

    try:
        summary = build_market_summary(records)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc

    result = {
        "analysis_id": str(uuid4()),
        "analysis_type": "stock" if symbol else "market",
        "trade_date": summary.trade_date,
        "generated_at": datetime.now(timezone.utc),
        "status": "complete",
        "market_metrics": {
            "nse_stocks": summary.nse_stocks,
            "positive": summary.nse_positive,
            "negative": summary.nse_negative,
            "unchanged": summary.nse_unchanged,
            "breadth_pct": summary.nse_breadth_pct,
            "mean_change_pct": summary.nse_mean_change_pct,
        },
        "regime": {"label": summary.regime.label, "reasons": summary.regime.reasons},
        "top_gainers": [item.__dict__ for item in summary.top_gainers],
        "top_losers": [item.__dict__ for item in summary.top_losers],
        "disclaimer": DISCLAIMER,
    }
    if symbol:
        symbol_upper=symbol.upper()
        matches=[r for r in records if r.exchange=="NSE" and r.symbol.upper()==symbol_upper]
        if not matches:
            raise HTTPException(404, f"No NSE EOD data found for {symbol}")
        result["selected_stock"]={
            "symbol":symbol_upper,
            "sessions": sorted([r.trade_date for r in matches])[-6:],
            "latest_close": sorted(matches,key=lambda r:r.trade_date)[-1].close,
        }

    await db.analyses.insert_one(result)
    return result
