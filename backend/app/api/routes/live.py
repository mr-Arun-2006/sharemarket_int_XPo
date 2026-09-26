from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.db.mongo import get_database
from app.services.live_hub import live_hub

router = APIRouter(prefix="/api/v1/live", tags=["live"])


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
async def ingest_tick(payload: LiveTickRequest):
    now = datetime.now(timezone.utc)
    document = payload.model_dump()
    document.update({"data_type": "live", "as_of": now})

    db = get_database()
    await db.market_data.insert_one(document)

    await live_hub.publish({
        "type": "market.tick",
        "data": {
            **payload.model_dump(),
            "data_status": "live",
            "as_of": now.isoformat(),
        },
    })

    return {"status": "published", "symbol": payload.symbol.upper()}


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
