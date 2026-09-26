from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket


@dataclass(frozen=True)
class LiveTick:
    exchange: str
    symbol: str
    name: str | None
    price: float | None
    previous_close: float | None
    change_pct: float | None
    volume: float | None
    as_of: str


class LiveHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self.broker = None

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def publish_local(self, payload: dict[str, Any]) -> None:
        async with self._lock:
            clients = list(self._clients)

        stale: list[WebSocket] = []
        for client in clients:
            try:
                await client.send_json(payload)
            except Exception:
                stale.append(client)

        for client in stale:
            await self.disconnect(client)

    async def publish(self, payload: dict[str, Any]) -> None:
        if self.broker and self.broker.client:
            await self.broker.publish(payload)
            return
        await self.publish_local(payload)

    def attach_broker(self, broker: Any) -> None:
        self.broker = broker

    @property
    def client_count(self) -> int:
        return len(self._clients)


live_hub = LiveHub()
