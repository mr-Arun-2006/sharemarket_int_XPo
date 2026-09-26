from datetime import datetime, timezone
import asyncio
import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.db.mongo import get_database
from app.api.deps.auth import get_current_user, get_user_from_access_token, require_permission
from app.core.config import settings
from app.services.live_hub import live_hub
from app.services.live_market import get_relevant_live_quotes, process_live_tick
from app.services.live_provider import live_provider
from app.services.redis_live import redis_live_broker

router = APIRouter(prefix="/api/v1/live", tags=["live"])


def extract_websocket_access_token(header_value: str | None) -> str | None:
    if not header_value:
        return None
    offered = [part.strip() for part in header_value.split(",") if part.strip()]
    try:
        auth_index = offered.index("sharem-auth")
    except ValueError:
        return None

    # Browser clients offer the protocol marker followed by the short-lived
    # access token. The token is never placed in the websocket URL.
    for candidate in offered[auth_index + 1:]:
        if candidate.count(".") == 2 and len(candidate) <= 4096:
            return candidate
    return None


async def require_live_ingest(
    x_live_ingest_key: str | None = Header(default=None),
    user: dict = Depends(get_current_user),
) -> dict:
    if settings.live_ingest_api_key:
        if x_live_ingest_key and hmac.compare_digest(
            x_live_ingest_key, settings.live_ingest_api_key
        ):
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
        "provider_configured": bool(settings.live_provider_url),
        "provider_running": live_provider.running,
        "redis_configured": bool(settings.redis_url),
        "redis_connected": redis_live_broker.client is not None,
        "max_connections": settings.live_max_connections,
        "heartbeat_seconds": settings.live_heartbeat_seconds,
    }


@router.post("/ingest")
async def ingest_tick(
    payload: LiveTickRequest,
    _: dict = Depends(require_live_ingest),
):
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
    token = extract_websocket_access_token(
        websocket.headers.get("sec-websocket-protocol")
    )
    if not token:
        await websocket.close(code=4401, reason="Authentication required")
        return

    try:
        await get_user_from_access_token(token)
    except HTTPException:
        await websocket.close(code=4401, reason="Authentication required")
        return

    try:
        await live_hub.connect(websocket)
    except RuntimeError:
        await websocket.close(code=1013, reason="Live market capacity reached")
        return

    try:
        await websocket.send_json(
            {
                "type": "market.status",
                "data": {
                    "status": "connected",
                    "transport": "websocket",
                    "data_status": "live",
                },
            }
        )

        while True:
            try:
                # A browser websocket is otherwise silent; periodic heartbeats
                # keep the connection visible through common reverse proxies.
                await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=settings.live_heartbeat_seconds,
                )
            except asyncio.TimeoutError:
                await websocket.send_json(live_hub.heartbeat_payload())
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await live_hub.disconnect(websocket)
