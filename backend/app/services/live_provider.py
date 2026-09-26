from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

from app.core.config import settings

logger = logging.getLogger(__name__)


class LiveProvider:
    def __init__(self) -> None:
        self.task: asyncio.Task | None = None
        self.running = False

    async def start(self, handler: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        if not settings.live_provider_url or self.running:
            return
        self.running = True
        self.task = asyncio.create_task(self._run(handler))

    async def stop(self) -> None:
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    async def _run(self, handler: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        import websockets

        delay = 2.0
        while self.running:
            try:
                extra_headers = {}
                if settings.live_provider_api_key:
                    extra_headers["Authorization"] = "Bearer " + settings.live_provider_api_key
                async with websockets.connect(
                    settings.live_provider_url,
                    additional_headers=extra_headers,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                    max_size=2 * 1024 * 1024,
                ) as connection:
                    delay = 2.0
                    subscribe = getattr(settings, "live_provider_subscribe_json", "")
                    if subscribe:
                        await connection.send(subscribe)
                    async for raw in connection:
                        try:
                            message = json.loads(raw)
                            tick = self._normalize_tick(message)
                            if tick:
                                await handler(tick)
                        except Exception:
                            logger.exception("Live provider message normalization failed")
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Live market provider connection failed")
                await asyncio.sleep(delay)
                delay = min(delay * 2.0, 30.0)

    @staticmethod
    def _normalize_tick(message: Any) -> dict[str, Any] | None:
        data = message.get("data", message) if isinstance(message, dict) else None
        if not isinstance(data, dict):
            return None
        exchange = data.get("exchange")
        symbol = data.get("symbol")
        price = data.get("price")
        if not exchange or not symbol or price in (None, ""):
            return None
        return {
            "exchange": str(exchange).upper(),
            "symbol": str(symbol).upper(),
            "name": data.get("name"),
            "price": float(price),
            "previous_close": float(data["previous_close"]) if data.get("previous_close") not in (None, "") else None,
            "change_pct": float(data["change_pct"]) if data.get("change_pct") not in (None, "") else None,
            "volume": float(data["volume"]) if data.get("volume") not in (None, "") else None,
            "unusual_activity": float(data["unusual_activity"]) if data.get("unusual_activity") not in (None, "") else 0.0,
            "event_flag": bool(data.get("event_flag")),
        }


live_provider = LiveProvider()
