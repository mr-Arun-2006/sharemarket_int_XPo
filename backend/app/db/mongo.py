from contextlib import asynccontextmanager
from typing import AsyncIterator

from pymongo import AsyncMongoClient

from app.core.config import settings

_client: AsyncMongoClient | None = None


@asynccontextmanager
async def mongo_lifespan() -> AsyncIterator[AsyncMongoClient]:
    global _client
    _client = AsyncMongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=10_000,
        connectTimeoutMS=10_000,
        socketTimeoutMS=30_000,
        retryWrites=True,
    )
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

    await db.user.create_index("user_id", unique=True, name="user_id_unique")
    await db.user.create_index("email_normalized", unique=True, name="user_email_unique")

    await db.sessions.create_index("session_id", unique=True, name="session_id_unique")
    await db.sessions.create_index("token_hash", unique=True, name="session_token_hash_unique")
    await db.sessions.create_index("expires_at", expireAfterSeconds=0, name="session_expiry_ttl")
    await db.sessions.create_index(
        [("user_id", 1), ("revoked_at", 1)],
        name="session_user_revoked",
    )

    await db.auth_challenges.create_index(
        "challenge_id",
        unique=True,
        sparse=True,
        name="auth_challenge_id_unique",
    )
    await db.auth_challenges.create_index(
        "expires_at",
        expireAfterSeconds=0,
        name="auth_challenge_expiry_ttl",
    )

    await db.rate_limits.create_index("key", unique=True, name="rate_limit_key_unique")
    await db.rate_limits.create_index(
        "expires_at",
        expireAfterSeconds=0,
        name="rate_limit_expiry_ttl",
    )

    await db.eod_market_data.create_index(
        [("exchange", 1), ("trade_date", -1), ("symbol", 1)],
        name="eod_exchange_date_symbol",
    )
    await db.ingestion_runs.create_index(
        [("dataset", 1), ("exchange", 1), ("trade_date", -1), ("fetched_at", -1)],
        name="ingestion_dataset_exchange_date",
    )
    await db.index_data.create_index(
        [("exchange", 1), ("trade_date", -1), ("symbol", 1)],
        name="index_exchange_date_symbol",
    )
    await db.fundamental_data.create_index(
        [("symbol", 1), ("as_of", -1), ("ingested_at", -1)],
        name="fundamental_symbol_asof",
    )
    await db.scheduler_locks.create_index(
        "lock_name",
        unique=True,
        name="scheduler_lock_unique",
    )
    await db.scheduler_locks.create_index(
        "expires_at",
        expireAfterSeconds=0,
        name="scheduler_lock_expiry_ttl",
    )
    await db.exchange_holidays.create_index(
        [("exchange", 1), ("date", 1)],
        unique=True,
        name="exchange_holiday_unique",
    )

    await db.analyses.create_index(
        [("user_id", 1), ("generated_at", -1)],
        name="analysis_user_generated",
    )
    await db.evidence.create_index("analysis_id", name="evidence_analysis_id")
    await db.reports.create_index(
        [("user_id", 1), ("generated_at", -1)],
        name="report_user_generated",
    )
    await db.backtest_runs.create_index(
        [("user_id", 1), ("created_at", -1)],
        name="backtest_user_created",
    )
    await db.portfolios.create_index(
        [("user_id", 1), ("name", 1)],
        unique=True,
        name="portfolio_user_name_unique",
    )
    await db.portfolio_holdings.create_index(
        [("portfolio_id", 1), ("user_id", 1), ("symbol", 1), ("exchange", 1)],
        unique=True,
        name="portfolio_holding_unique",
    )
    await db.portfolio_transactions.create_index(
        [("portfolio_id", 1), ("user_id", 1), ("trade_date", -1)],
        name="portfolio_transactions_date",
    )
    await db.audit_logs.create_index([("created_at", -1)], name="audit_created_at")


def get_mongo_client() -> AsyncMongoClient:
    if _client is None:
        raise RuntimeError("MongoDB client is not initialized")
    return _client


def get_database():
    return get_mongo_client()[settings.mongodb_database]
