from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone
from typing import Any

from app.db.mongo import get_database


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.strip().lower())


def _value(row: dict[str, Any], *aliases: str) -> Any:
    normalized = {_key(str(k)): v for k, v in row.items()}
    for alias in aliases:
        value = normalized.get(_key(alias))
        if value not in (None, ""):
            return value
    return None


def normalize_date(value: Any) -> str:
    raw = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%B-%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return raw


def parse_holiday_csv(data: bytes) -> list[dict[str, str]]:
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict[str, str]] = []
    for raw in reader:
        exchange = str(_value(raw, "exchange", "market") or "").strip().upper()
        date = normalize_date(_value(raw, "date", "holidaydate", "holiday_date"))
        description = str(_value(raw, "description", "holiday", "name") or "").strip()
        if exchange in {"NSE", "BSE"} and date:
            rows.append({"exchange": exchange, "date": date, "description": description})
    return rows


async def ingest_holidays(rows: list[dict[str, str]], source: str, ingestion_id: str) -> int:
    db = get_database()
    now = datetime.now(timezone.utc)
    for row in rows:
        await db.exchange_holidays.update_one(
            {"exchange": row["exchange"], "date": row["date"]},
            {"$set": {**row, "source": source, "ingestion_id": ingestion_id, "updated_at": now}},
            upsert=True,
        )
    return len(rows)


async def get_holiday(exchange: str, date: str) -> dict[str, Any] | None:
    return await get_database().exchange_holidays.find_one(
        {"exchange": exchange, "date": date},
        {"_id": 0},
    )
