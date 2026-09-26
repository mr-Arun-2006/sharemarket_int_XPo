from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.services.remote_ingestion import ingest_remote_eod
from app.services.index_data import ingest_remote_index

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")
scheduler = AsyncIOScheduler(timezone=IST)

from app.db.mongo import get_database

async def _record_failure(dataset: str, exchange: str, trade_date, source: str, error: str) -> None:
    await get_database().ingestion_runs.insert_one({
        "dataset": dataset,
        "exchange": exchange,
        "trade_date": trade_date.isoformat(),
        "source": source,
        "status": "failed",
        "error": error[:2000],
        "fetched_at": datetime.now(IST),
    })


async def run_scheduled_ingestion() -> dict:
    results = []
    today = datetime.now(IST).date()
    sources = [
        ("NSE", settings.nse_eod_url_template),
        ("BSE", settings.bse_eod_url_template),
    ]
    for exchange, template in sources:
        if not template:
            results.append({"exchange": exchange, "status": "not_configured"})
            continue
        try:
            results.append(await ingest_remote_eod(exchange, template, today))
        except Exception as exc:
            logger.exception("%s EOD ingestion failed", exchange)
            await _record_failure("eod_market_data", exchange, today, template, str(exc))
            results.append({"exchange": exchange, "status": "failed", "error": str(exc)})

    for exchange, template in [("NSE", settings.nse_index_url_template), ("BSE", settings.bse_index_url_template)]:
        if not template:
            results.append({"exchange": exchange, "dataset": "index_data", "status": "not_configured"})
            continue
        try:
            results.append(await ingest_remote_index(template, exchange, today))
        except Exception as exc:
            logger.exception("%s index ingestion failed", exchange)
            await _record_failure("index_data", exchange, today, template, str(exc))
            results.append({"exchange": exchange, "dataset": "index_data", "status": "failed", "error": str(exc)})
    return {"trade_date": today.isoformat(), "results": results}


def start_scheduler() -> None:
    if not settings.data_scheduler_enabled or scheduler.running:
        return
    scheduler.add_job(
        run_scheduled_ingestion,
        CronTrigger(day_of_week="mon-fri", hour=15, minute=45, timezone=IST),
        id="eod-market-ingestion",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
