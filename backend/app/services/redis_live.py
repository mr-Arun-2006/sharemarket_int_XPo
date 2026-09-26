from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

CHANNEL = "sharem:market:ticks"


class RedisLiveBroker:
    def __init__(self) -> None:
        self.client: Redis | None = None
        self.task: asyncio.Task | None = None
        self._handler: Callable[[dict[str, Any]], Awaitable[None]] | None = None

    async def start(self, handler: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        self._handler = handler
        if not settings.redis_url:
            return
        self.client = Redis.from_url(settings.redis_url, decode_responses=True)
        await self.client.ping()
        self.task = asyncio.create_task(self._subscribe())

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
        if self.client:
            await self.client.aclose()
            self.client = None

    async def publish(self, payload: dict[str, Any]) -> None:
        if self.client:
            await self.client.publish(
                CHANNEL,
                json.dumps(payload, default=str, ensure_ascii=False),
            )

    async def _subscribe(self) -> None:
        if not self.client or not self._handler:
            return
        pubsub = self.client.pubsub()
        await pubsub.subscribe(CHANNEL)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                try:
                    payload = json.loads(message["data"])
                    await self._handler(payload)
                except Exception:
                    logger.exception("Invalid Redis market message")
        finally:
            await pubsub.close()


redis_live_broker = RedisLiveBroker()
