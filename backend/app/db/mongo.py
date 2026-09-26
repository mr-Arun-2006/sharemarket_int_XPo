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
        await _ensure_indexes()
        start_scheduler()
        yield _client
    finally:
        stop_scheduler()
        await live_provider.stop()
        await redis_live_broker.stop()
        await _client.close()
        _client = None



async def _ensure_indexes() -> None:
    db = get_database()
    await db.rate_limits.create_index("key", unique=True, name="rate_limit_key_unique")
    await db.rate_limits.create_index("expires_at", expireAfterSeconds=0, name="rate_limit_expiry_ttl")
    await db.fundamental_data.create_index(
        [("symbol", 1), ("as_of", -1)],
        name="fundamental_symbol_asof",
    )
    await db.scheduler_locks.create_index("lock_name", unique=True, name="scheduler_lock_unique")
    await db.scheduler_locks.create_index("expires_at", expireAfterSeconds=0, name="scheduler_lock_expiry_ttl")


def get_mongo_client() -> AsyncMongoClient:
    if _client is None:
        raise RuntimeError("MongoDB client is not initialized")
    return _client


def get_database():
    return get_mongo_client()[settings.mongodb_database]
