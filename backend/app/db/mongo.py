from contextlib import asynccontextmanager
from typing import AsyncIterator

from pymongo import AsyncMongoClient

from app.core.config import settings

_client: AsyncMongoClient | None = None


@asynccontextmanager
async def mongo_lifespan() -> AsyncIterator[AsyncMongoClient]:
    global _client
    _client = AsyncMongoClient(settings.mongodb_uri)
    await _client.admin.command("ping")
    from app.services.scheduler import start_scheduler, stop_scheduler
    from app.services.live_hub import live_hub
    from app.services.redis_live import redis_live_broker
    from app.services.live_provider import live_provider
    from app.services.live_market import process_live_tick

    live_hub.attach_broker(redis_live_broker)
    try:
        await redis_live_broker.start(live_hub.publish_local)
        await live_provider.start(process_live_tick)
        start_scheduler()
        yield _client
    finally:
        stop_scheduler()
        await live_provider.stop()
        await redis_live_broker.stop()
        await _client.close()
        _client = None


def get_mongo_client() -> AsyncMongoClient:
    if _client is None:
        raise RuntimeError("MongoDB client is not initialized")
    return _client


def get_database():
    return get_mongo_client()[settings.mongodb_database]
