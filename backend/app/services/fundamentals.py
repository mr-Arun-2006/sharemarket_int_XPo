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


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def _normalize_date(value: Any) -> str:
    raw = str(value or "").strip()
    for candidate in (raw, raw.split(" ")[0]):
        for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%B-%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(candidate, fmt).date().isoformat()
            except ValueError:
                continue
    return raw


def parse_fundamentals_csv(data: bytes) -> list[dict[str, Any]]:
    text = data.decode("utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",|;\t")
    except csv.Error:
        dialect = csv.excel

    rows: list[dict[str, Any]] = []
    for raw in csv.DictReader(io.StringIO(text), dialect=dialect):
        symbol = _value(raw, "symbol", "security", "securitysymbol", "scrip", "ticker")
        if not symbol:
            continue
        as_of = _normalize_date(_value(raw, "asof", "as_of", "date", "reportdate", "periodend"))
        rows.append({
            "symbol": str(symbol).strip().upper(),
            "as_of": as_of,
            "company_name": _value(raw, "company", "companyname", "name"),
            "market_cap": _float(_value(raw, "marketcap", "market_cap")),
            "enterprise_value": _float(_value(raw, "enterprisevalue", "enterprise_value", "ev")),
            "revenue": _float(_value(raw, "revenue", "sales")),
            "net_income": _float(_value(raw, "netincome", "profit", "pat")),
            "eps": _float(_value(raw, "eps", "earningspershare")),
            "pe": _float(_value(raw, "pe", "pe_ratio", "peratio")),
            "pb": _float(_value(raw, "pb", "pb_ratio", "pbratio")),
            "roe_pct": _float(_value(raw, "roe", "roe_pct", "returnonequity")),
            "roce_pct": _float(_value(raw, "roce", "roce_pct")),
            "debt_to_equity": _float(_value(raw, "debtequity", "debt_to_equity", "d_e")),
            "dividend_yield_pct": _float(_value(raw, "dividendyield", "dividend_yield")),
            "source": _value(raw, "source") or "admin-upload",
            "source_url": _value(raw, "url", "sourceurl", "link"),
        })
    return rows


async def get_fundamental_snapshot(symbol: str, as_of: str | None = None) -> dict[str, Any] | None:
    db = get_database()
    query: dict[str, Any] = {"symbol": symbol.upper()}
    if as_of:
        query["as_of"] = {"$lte": as_of}
    return await db.fundamental_data.find_one(
        query,
        {"_id": 0},
        sort=[("as_of", -1), ("ingested_at", -1)],
    )


async def upsert_fundamentals(rows: list[dict[str, Any]], source: str, ingestion_id: str) -> int:
    if not rows:
        return 0
    db = get_database()
    now = datetime.now(timezone.utc)
    operations = []
    for row in rows:
        document = {
            **row,
            "source": row.get("source") or source,
            "ingestion_id": ingestion_id,
            "ingested_at": now,
        }
        operations.append(document)

    count = 0
    for document in operations:
        await db.fundamental_data.update_one(
            {"symbol": document["symbol"], "as_of": document["as_of"], "source": document["source"]},
            {"$set": document},
            upsert=True,
        )
        count += 1
    return count
