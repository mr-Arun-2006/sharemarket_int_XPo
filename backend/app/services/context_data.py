from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone
from typing import Any

from app.db.mongo import get_database


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.strip().lower())


def _value(row: dict[str, Any], *aliases: str):
    normalized = {_key(str(k)): v for k, v in row.items()}
    for alias in aliases:
        v = normalized.get(_key(alias))
        if v not in (None, ""):
            return v
    return None


def _float(value: Any):
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def parse_context_csv(data: bytes, kind: str) -> list[dict[str, Any]]:
    text = data.decode("utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",|;\t")
    except csv.Error:
        dialect = csv.excel

    rows = []
    for raw in csv.DictReader(io.StringIO(text), dialect=dialect):
        if kind == "sector":
            symbol = _value(raw, "symbol", "security", "securitysymbol", "scrip")
            sector = _value(raw, "sector", "industry", "sectorname")
            if symbol and sector:
                rows.append({
                    "symbol": str(symbol).strip().upper(),
                    "sector": str(sector).strip(),
                    "industry": _value(raw, "industry", "industryname"),
                    "source": _value(raw, "source") or "exchange",
                })
        elif kind == "institutional":
            trade_date = _value(raw, "date", "tradedate", "trade_date", "businessdate")
            category = _value(raw, "category", "investorcategory", "investortype")
            buy = _float(_value(raw, "buyvalue", "buy_value", "buy"))
            sell = _float(_value(raw, "sellvalue", "sell_value", "sell"))
            net = _float(_value(raw, "netvalue", "net_value", "net"))
            if trade_date and category and (buy is not None or sell is not None or net is not None):
                if net is None and buy is not None and sell is not None:
                    net = buy - sell
                rows.append({
                    "trade_date": str(trade_date).strip(),
                    "category": str(category).strip(),
                    "buy_value": buy,
                    "sell_value": sell,
                    "net_value": net,
                    "source": _value(raw, "source") or "exchange",
                })
        elif kind == "event":
            symbol = _value(raw, "symbol", "security", "securitysymbol", "company")
            subject = _value(raw, "subject", "headline", "title")
            details = _value(raw, "details", "description", "remark", "text")
            broadcast = _value(raw, "broadcasttime", "broadcast_at", "datetime", "date", "announcementdate")
            if subject or details:
                rows.append({
                    "symbol": str(symbol).strip().upper() if symbol else None,
                    "subject": str(subject or "").strip(),
                    "details": str(details or "").strip(),
                    "broadcast_at": str(broadcast or "").strip(),
                    "source": _value(raw, "source") or "exchange",
                    "source_url": _value(raw, "url", "sourceurl", "link"),
                })
    return rows


async def build_market_context(trade_date: str) -> dict[str, Any]:
    db = get_database()

    sector_rows = await db.sector_data.find(
        {}, {"_id": 0, "symbol": 1, "sector": 1, "industry": 1, "source": 1}
    ).to_list(length=20000)
    sector_map = {row["symbol"].upper(): row for row in sector_rows if row.get("symbol") and row.get("sector")}

    market_rows = await db.eod_market_data.find(
        {"exchange": "NSE", "trade_date": trade_date},
        {"_id": 0, "symbol": 1, "close": 1, "previous_close": 1, "volume": 1},
    ).to_list(length=10000)

    aggregates: dict[str, list[float]] = {}
    sector_counts: dict[str, dict[str, int]] = {}
    for row in market_rows:
        mapping = sector_map.get(str(row.get("symbol", "")).upper())
        if not mapping:
            continue
        close = _float(row.get("close"))
        previous = _float(row.get("previous_close"))
        if close is None or previous in (None, 0):
            continue
        change = (close - previous) / previous * 100
        sector = mapping["sector"]
        aggregates.setdefault(sector, []).append(change)
        bucket = sector_counts.setdefault(sector, {"positive": 0, "negative": 0, "unchanged": 0})
        if change > 0: bucket["positive"] += 1
        elif change < 0: bucket["negative"] += 1
        else: bucket["unchanged"] += 1

    sectors = []
    for sector, changes in aggregates.items():
        counts = sector_counts[sector]
        sectors.append({
            "sector": sector,
            "stocks_covered": len(changes),
            "average_change_pct": sum(changes) / len(changes),
            **counts,
        })
    sectors.sort(key=lambda x: x["average_change_pct"], reverse=True)

    institutional = await db.institutional_activity.find(
        {"trade_date": trade_date},
        {"_id": 0, "category": 1, "buy_value": 1, "sell_value": 1, "net_value": 1, "source": 1},
    ).to_list(length=50)

    events = await db.market_events.find(
        {}, {"_id": 0, "symbol": 1, "subject": 1, "details": 1, "broadcast_at": 1, "source": 1, "source_url": 1}
    ).to_list(length=500)
    events = [e for e in events if not e.get("broadcast_at") or str(e["broadcast_at"]).startswith(trade_date)]
    events.sort(key=lambda x: x.get("broadcast_at") or "", reverse=True)

    return {
        "sectors": sectors,
        "sector_coverage": {"mapped_symbols": len(sector_map), "sectors_found": len(sectors)},
        "institutional_activity": institutional,
        "major_events": events[:100],
    }
