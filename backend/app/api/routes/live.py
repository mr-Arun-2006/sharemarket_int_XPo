from datetime import datetime, timezone
import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.db.mongo import get_database
from app.api.deps.auth import get_current_user, require_permission
from app.core.config import settings
from app.services.live_hub import live_hub
from app.services.live_market import get_relevant_live_quotes, process_live_tick

router = APIRouter(prefix="/api/v1/live", tags=["live"])

async def require_live_ingest(
    x_live_ingest_key: str | None = Header(default=None),
    user: dict = Depends(get_current_user),
) -> dict:
    if settings.live_ingest_api_key:
        if x_live_ingest_key and hmac.compare_digest(x_live_ingest_key, settings.live_ingest_api_key):
            return {"service": True, "user": user}
        raise HTTPException(403, "Invalid live-ingest service key")
    if user.get("role") == "admin":
        return {"service": False, "user": user}
    role = await get_database().roles.find_one({"name": user.get("role")})
    permissions = set(role.get("permissions", [])) if role else set()
    if "*" in permissions or "admin.data.manage" in permissions:
        return {"service": False, "user": user}
    raise HTTPException(403, "Live ingestion permission is required")



class LiveTickRequest(BaseModel):
    exchange: str = Field(pattern="^(NSE|BSE)$")
    symbol: str = Field(min_length=1, max_length=32)
    name: str | None = None
    price: float | None = None
    previous_close: float | None = None
    change_pct: float | None = None
    volume: float | None = None


@router.get("/status")
async def live_status():
    return {
        "status": "connected" if live_hub.client_count else "idle",
        "clients": live_hub.client_count,
        "transport": "websocket",
    }


@router.post("/ingest")
async def ingest_tick(payload: LiveTickRequest, _: dict = Depends(require_live_ingest)):
    return await process_live_tick(payload.model_dump())


@router.get("/relevant")
async def relevant_live_quotes(
    limit: int = 20,
    _: dict = Depends(require_permission("market.read")),
):
    limit = max(1, min(limit, 100))
    return {"quotes": await get_relevant_live_quotes(limit)}

@router.websocket("/ws")
async def market_websocket(websocket: WebSocket):
    await live_hub.connect(websocket)
    try:
        await websocket.send_json({
            "type": "market.status",
            "data": {
                "status": "connected",
                "transport": "websocket",
                "data_status": "live",
            },
        })

        while True:
            # Client messages are intentionally ignored for this read-only market stream.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await live_hub.disconnect(websocket)
    except Exception:
        await live_hub.disconnect(websocket)
