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
    try:
        yield _client
    finally:
        await _client.close()
        _client = None

def get_mongo_client() -> AsyncMongoClient:
    if _client is None:
        raise RuntimeError("MongoDB client is not initialized")
    return _client

def get_database():
    return get_mongo_client()[settings.mongodb_database]
