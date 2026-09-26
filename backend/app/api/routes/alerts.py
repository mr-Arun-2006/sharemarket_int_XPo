from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps.auth import get_current_user, require_permission
from app.db.mongo import get_database
from app.services.audit import record_audit

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])

ALERT_TYPES = {"price", "percent_change", "volume", "technical", "ai_event", "sentiment", "regime"}
OPERATORS = {">", ">=", "<", "<=", "=="}


class AlertCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    alert_type: str = Field(min_length=3, max_length=32)
    exchange: str = Field(default="NSE", pattern="^(NSE|BSE)$")
    symbol: str = Field(min_length=1, max_length=32)
    operator: str = Field(default=">=", max_length=2)
    threshold: float | None = None
    indicator: str | None = Field(default=None, max_length=32)
    channel: str = Field(default="in_app", pattern="^(in_app|email|both)$")
    cooldown_minutes: int = Field(default=5, ge=1, le=1440)


class AlertUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    enabled: bool | None = None
    operator: str | None = Field(default=None, max_length=2)
    threshold: float | None = None
    indicator: str | None = Field(default=None, max_length=32)
    channel: str | None = Field(default=None, pattern="^(in_app|email|both)$")
    cooldown_minutes: int | None = Field(default=None, ge=1, le=1440)


@router.get("")
async def list_alerts(current_user: dict = Depends(get_current_user)):
    rows = await get_database().alerts.find(
        {"user_id": current_user["user_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(length=200)
    return {"alerts": rows}


@router.post("", status_code=201)
async def create_alert(payload: AlertCreate, current_user: dict = Depends(require_permission("alerts.manage"))):
    if payload.alert_type not in ALERT_TYPES:
        raise HTTPException(400, "Unsupported alert type")
    if payload.operator not in OPERATORS:
        raise HTTPException(400, "Unsupported operator")
    if payload.alert_type in {"price", "percent_change", "volume", "technical"} and payload.threshold is None:
        raise HTTPException(400, "A numeric threshold is required for this alert type")
    alert_id = secrets.token_urlsafe(18)
    now = datetime.now(timezone.utc)
    document = {
        "alert_id": alert_id,
        "user_id": current_user["user_id"],
        "name": payload.name,
        "alert_type": payload.alert_type,
        "exchange": payload.exchange,
        "symbol": payload.symbol.upper(),
        "operator": payload.operator,
        "threshold": payload.threshold,
        "indicator": payload.indicator,
        "channel": payload.channel,
        "cooldown_minutes": payload.cooldown_minutes,
        "enabled": True,
        "created_at": now,
        "updated_at": now,
        "last_triggered_at": None,
    }
    await get_database().alerts.insert_one(document)
    await record_audit("alert.created", user_id=current_user["user_id"], target_type="alert", target_id=alert_id)
    return {k: v for k, v in document.items() if k != "_id"}


@router.patch("/{alert_id}")
async def update_alert(alert_id: str, payload: AlertUpdate, current_user: dict = Depends(require_permission("alerts.manage"))):
    db = get_database()
    alert = await db.alerts.find_one({"alert_id": alert_id, "user_id": current_user["user_id"]})
    if not alert:
        raise HTTPException(404, "Alert not found")
    updates = payload.model_dump(exclude_none=True)
    if "operator" in updates and updates["operator"] not in OPERATORS:
        raise HTTPException(400, "Unsupported operator")
    if "channel" in updates and updates["channel"] not in {"in_app", "email", "both"}:
        raise HTTPException(400, "Unsupported channel")
    updates["updated_at"] = datetime.now(timezone.utc)
    await db.alerts.update_one({"_id": alert["_id"]}, {"$set": updates})
    await record_audit("alert.updated", user_id=current_user["user_id"], target_type="alert", target_id=alert_id)
    return {"status": "updated", "alert_id": alert_id}


@router.delete("/{alert_id}")
async def delete_alert(alert_id: str, current_user: dict = Depends(require_permission("alerts.manage"))):
    db = get_database()
    result = await db.alerts.delete_one({"alert_id": alert_id, "user_id": current_user["user_id"]})
    if not result.deleted_count:
        raise HTTPException(404, "Alert not found")
    await record_audit("alert.deleted", user_id=current_user["user_id"], target_type="alert", target_id=alert_id)
    return {"status": "deleted", "alert_id": alert_id}


@router.get("/events")
async def list_alert_events(
    limit: int = Query(default=100, ge=1, le=300),
    current_user: dict = Depends(get_current_user),
):
    rows = await get_database().alert_events.find(
        {"user_id": current_user["user_id"]}, {"_id": 0}
    ).sort("triggered_at", -1).to_list(length=limit)
    return {"events": rows}
