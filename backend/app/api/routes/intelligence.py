from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps.auth import get_current_user, require_permission
from app.db.mongo import get_database
from app.services.ai_provider import generate_narrative
from app.services.eod_engine import build_market_summary
from app.services.intelligence import SUPPORTED_LANGUAGES, build_ai_diagnosis
from app.schemas.market import EODRecord

router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])

DISCLAIMER = "For informational purposes only. This is not investment advice."


async def _load_eod_records(db, limit: int = 30000) -> list[EODRecord]:
    cursor = db.eod_market_data.find({}, {"_id": 0}).sort([("trade_date", -1)])
    rows: list[EODRecord] = []
    async for document in cursor:
        if len(rows) >= limit:
            break
        try:
            rows.append(EODRecord.model_validate(document))
        except Exception:
            continue
    return rows


@router.post("/eod")
async def generate_eod_intelligence(
    symbol: str | None = Query(default=None, max_length=32),
    language: str = Query(default="en", pattern="^(en|ta|hi|gu|kn)$"),
    current_user: dict = Depends(get_current_user),
):
    if symbol and current_user.get("role") != "admin":
        role = await get_database().roles.find_one({"name": current_user.get("role")})
        permissions = set(role.get("permissions", [])) if role else set()
        if "analysis.deep" not in permissions and "*" not in permissions:
            raise HTTPException(403, "Deep stock analysis permission is required")

    db = get_database()
    records = await _load_eod_records(db)
    if not records:
        raise HTTPException(404, "No EOD dataset is available")

    try:
        summary = build_market_summary(records)
        diagnosis = build_ai_diagnosis(summary, records, language=language, symbol=symbol)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc

    provider = await generate_narrative({
        "trade_date": summary.trade_date,
        "analysis_type": "stock" if symbol else "market",
        "language": SUPPORTED_LANGUAGES.get(language, "English"),
        "diagnosis": diagnosis,
    })

    analysis_id = str(uuid4())
    result = {
        "analysis_id": analysis_id,
        "analysis_type": "stock" if symbol else "market",
        "trade_date": summary.trade_date,
        "generated_at": datetime.now(timezone.utc),
        "status": "complete",
        "language": language,
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
        "hierarchy": diagnosis["sections"],
        "evidence": diagnosis["evidence"],
        "uncertainty": diagnosis["uncertainty"],
        "ai_provider": provider["status"],
        "ai_narrative": provider.get("narrative"),
        "disclaimer": DISCLAIMER,
    }

    await db.analyses.insert_one(result)

    if result["evidence"]:
        await db.evidence.delete_many({"analysis_id": analysis_id})
        await db.evidence.insert_many([
            {"analysis_id": analysis_id, **item, "created_at": result["generated_at"]}
            for item in result["evidence"]
        ], ordered=False)

    return result


@router.get("/history")
async def intelligence_history(
    q: str | None = Query(default=None, max_length=64),
    analysis_type: str | None = Query(default=None, pattern="^(market|stock)$"),
    language: str | None = Query(default=None, pattern="^(en|ta|hi|gu|kn)$"),
    limit: int = Query(default=30, ge=1, le=100),
    _: dict = Depends(require_permission("reports.read")),
):
    db = get_database()
    query = {}
    if q:
        query["$or"] = [
            {"analysis_id": {"$regex": q, "$options": "i"}},
            {"hierarchy.selected_stock.symbol": {"$regex": q, "$options": "i"}},
        ]
    if analysis_type:
        query["analysis_type"] = analysis_type
    if language:
        query["language"] = language
    rows = await db.analyses.find(
        query,
        {"_id": 0, "analysis_id": 1, "analysis_type": 1, "trade_date": 1, "generated_at": 1, "language": 1, "status": 1, "ai_provider": 1, "hierarchy.market.diagnosis": 1, "hierarchy.selected_stock.symbol": 1},
    ).sort("generated_at", -1).to_list(length=limit)
    return {"analyses": rows, "count": len(rows)}
