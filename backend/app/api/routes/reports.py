from __future__ import annotations

from datetime import datetime, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.api.deps.auth import require_permission
from app.db.mongo import get_database
from app.services.report_pdf import build_report_pdf

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def _title(analysis: dict) -> str:
    if analysis.get("analysis_type") == "stock":
        symbol = ((analysis.get("hierarchy") or {}).get("selected_stock") or {}).get("symbol", "Stock")
        return f"{symbol} EOD Intelligence Report"
    return "NSE EOD Market Intelligence Report"


@router.post("/from-analysis/{analysis_id}", status_code=201)
async def create_report(
    analysis_id: str,
    current_user: dict = Depends(require_permission("reports.read")),
):
    db = get_database()
    analysis = await db.analyses.find_one(
        {"analysis_id": analysis_id, "user_id": current_user["user_id"]},
        {"_id": 0},
    )
    if not analysis:
        raise HTTPException(404, "Analysis not found")

    report_id = secrets.token_urlsafe(18)
    now = datetime.now(timezone.utc)
    report = {
        "report_id": report_id,
        "user_id": current_user["user_id"],
        "analysis_id": analysis_id,
        "report_type": analysis.get("analysis_type", "market"),
        "title": _title(analysis),
        "trade_date": analysis.get("trade_date"),
        "language": analysis.get("language", "en"),
        "generated_at": now,
        "source_analysis_generated_at": analysis.get("generated_at"),
        "format": "pdf",
        "status": "ready",
    }
    await db.reports.insert_one(report)
    return report


@router.get("")
async def list_reports(
    report_type: str | None = Query(default=None, pattern="^(market|stock)$"),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: dict = Depends(require_permission("reports.read")),
):
    query = {"user_id": current_user["user_id"]}
    if report_type:
        query["report_type"] = report_type
    rows = await get_database().reports.find(
        query,
        {"_id": 0},
    ).sort("generated_at", -1).to_list(length=limit)
    return {"reports": rows, "count": len(rows)}


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    current_user: dict = Depends(require_permission("reports.read")),
):
    row = await get_database().reports.find_one(
        {"report_id": report_id, "user_id": current_user["user_id"]},
        {"_id": 0},
    )
    if not row:
        raise HTTPException(404, "Report not found")
    return row


@router.get("/{report_id}/pdf")
async def download_report_pdf(
    report_id: str,
    current_user: dict = Depends(require_permission("reports.read")),
):
    db = get_database()
    report = await db.reports.find_one(
        {"report_id": report_id, "user_id": current_user["user_id"]},
        {"_id": 0},
    )
    if not report:
        raise HTTPException(404, "Report not found")

    analysis = await db.analyses.find_one(
        {
            "analysis_id": report["analysis_id"],
            "user_id": current_user["user_id"],
        },
        {"_id": 0},
    )
    if not analysis:
        raise HTTPException(404, "Source analysis no longer exists")

    report_payload = {
        **report,
        "analysis_type": analysis.get("analysis_type"),
        "language": analysis.get("language", report.get("language", "en")),
        "market_metrics": analysis.get("market_metrics"),
        "regime": analysis.get("regime", {}),
        "summary": {
            "diagnosis": ((analysis.get("hierarchy") or {}).get("market") or {}).get("diagnosis")
                or (analysis.get("regime") or {}).get("label"),
            "regime": (analysis.get("regime") or {}).get("label"),
            "key_reasons": ((analysis.get("hierarchy") or {}).get("market") or {}).get("key_reasons")
                or (analysis.get("regime") or {}).get("reasons")
                or [],
        },
        "selected_stock": ((analysis.get("hierarchy") or {}).get("selected_stock")),
        "top_gainers": analysis.get("top_gainers", []),
        "top_losers": analysis.get("top_losers", []),
        "ai_narrative": analysis.get("ai_narrative"),
        "evidence": analysis.get("evidence", []),
        "uncertainty": analysis.get("uncertainty", []),
        "disclaimer": analysis.get("disclaimer"),
        "data_status": analysis.get("status", "complete"),
    }

    pdf = build_report_pdf(report_payload)
    filename = report["report_id"] + ".pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
