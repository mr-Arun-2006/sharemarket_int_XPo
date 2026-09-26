from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from app.db.mongo import get_database
from app.services.alert_engine import evaluate_live_tick
from app.services.live_hub import live_hub


def compute_live_relevance(tick: dict[str, Any]) -> float:
    change = abs(float(tick.get("change_pct") or 0.0))
    volume = float(tick.get("volume") or 0.0)
    unusual = float(tick.get("unusual_activity") or 0.0)
    event_boost = 1.0 if tick.get("event_flag") else 0.0
    move_component = min(change / 5.0, 1.0) * 60.0
    volume_component = min(math.log10(max(volume, 1.0)) / 8.0, 1.0) * 20.0
    unusual_component = min(max(unusual, 0.0), 1.0) * 15.0
    event_component = event_boost * 5.0
    return round(min(move_component + volume_component + unusual_component + event_component, 100.0), 2)


async def process_live_tick(payload: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    normalized = dict(payload)
    normalized["exchange"] = str(payload.get("exchange", "")).upper()
    normalized["symbol"] = str(payload.get("symbol", "")).upper()
    normalized["data_type"] = "live"
    normalized["as_of"] = now
    normalized["relevance_score"] = compute_live_relevance(payload)

    db = get_database()
    await db.market_data.update_one(
        {
            "exchange": normalized["exchange"],
            "symbol": normalized["symbol"],
        },
        {"$set": normalized},
        upsert=True,
    )

    triggered_alerts = await evaluate_live_tick(normalized)
    await live_hub.publish({
        "type": "market.tick",
        "data": {
            **{k: v for k, v in normalized.items() if k not in {"as_of", "data_type"}},
            "data_status": "live",
            "as_of": now.isoformat(),
        },
    })
    return {
        "status": "published",
        "symbol": normalized["symbol"],
        "exchange": normalized["exchange"],
        "relevance_score": normalized["relevance_score"],
        "triggered_alerts": triggered_alerts,
    }


async def get_relevant_live_quotes(limit: int = 20) -> list[dict[str, Any]]:
    db = get_database()
    rows = await db.market_data.find(
        {"data_type": "live"},
        {"_id": 0},
    ).sort("relevance_score", -1).to_list(length=limit)
    return rows
