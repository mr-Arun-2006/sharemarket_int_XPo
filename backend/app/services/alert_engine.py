from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db.mongo import get_database


def _compare(value: float | None, operator: str, threshold: float | None) -> bool:
    if value is None or threshold is None:
        return False
    return {
        ">": value > threshold,
        ">=": value >= threshold,
        "<": value < threshold,
        "<=": value <= threshold,
        "==": value == threshold,
    }.get(operator, False)


async def evaluate_live_tick(tick: dict) -> int:
    db = get_database()
    now = datetime.now(timezone.utc)
    alerts = await db.alerts.find({
        "enabled": True,
        "exchange": tick.get("exchange"),
        "symbol": str(tick.get("symbol", "")).upper(),
        "alert_type": {"$in": ["price", "percent_change", "volume"]},
    }, {"_id": 0}).to_list(length=500)

    triggered = 0
    for alert in alerts:
        last = alert.get("last_triggered_at")
        cooldown = timedelta(minutes=int(alert.get("cooldown_minutes", 5)))
        if last and now - last < cooldown:
            continue
        field = {"price": "price", "percent_change": "change_pct", "volume": "volume"}[alert["alert_type"]]
        value = tick.get(field)
        if not _compare(value, alert.get("operator", ">="), alert.get("threshold")):
            continue
        event_id = f"{alert['alert_id']}:{int(now.timestamp())}"
        event = {
            "event_id": event_id,
            "alert_id": alert["alert_id"],
            "user_id": alert["user_id"],
            "alert_name": alert["name"],
            "alert_type": alert["alert_type"],
            "exchange": tick.get("exchange"),
            "symbol": tick.get("symbol"),
            "value": value,
            "threshold": alert.get("threshold"),
            "operator": alert.get("operator"),
            "channel": alert.get("channel", "in_app"),
            "triggered_at": now,
            "source": "live_websocket_tick",
        }
        try:
            await db.alert_events.insert_one(event)
        except Exception:
            continue
        await db.alerts.update_one(
            {"alert_id": alert["alert_id"]},
            {"$set": {"last_triggered_at": now, "updated_at": now}},
        )
        triggered += 1
    return triggered
