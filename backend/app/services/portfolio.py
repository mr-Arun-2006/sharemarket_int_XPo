from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.db.mongo import get_database
from app.services.technical import compute_technical_snapshot
from app.schemas.market import EODRecord


def _pct(close, previous):
    if close is None or previous in (None, 0):
        return None
    return (close - previous) / previous * 100


async def _latest_quotes(symbols: list[tuple[str, str]]) -> dict[tuple[str, str], dict[str, Any]]:
    if not symbols:
        return {}
    db = get_database()
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for exchange, symbol in symbols:
        row = await db.eod_market_data.find_one(
            {"exchange": exchange, "symbol": symbol.upper()},
            {"_id": 0, "trade_date": 1, "close": 1, "previous_close": 1, "volume": 1, "name": 1},
            sort=[("trade_date", -1)],
        )
        if row:
            result[(exchange, symbol.upper())] = {
                **row,
                "change_pct": _pct(row.get("close"), row.get("previous_close")),
                "data_status": "eod",
            }
    return result


async def build_portfolio_snapshot(portfolio_id: str, user_id: str) -> dict:
    db = get_database()
    portfolio = await db.portfolios.find_one(
        {"portfolio_id": portfolio_id, "user_id": user_id}, {"_id": 0}
    )
    if not portfolio:
        raise ValueError("Portfolio not found")

    holdings = await db.portfolio_holdings.find(
        {"portfolio_id": portfolio_id, "user_id": user_id}, {"_id": 0}
    ).sort("symbol", 1).to_list(length=500)

    quotes = await _latest_quotes([(h["exchange"], h["symbol"]) for h in holdings])

    enriched = []
    total_value = total_cost = 0.0
    daily_pnl = 0.0
    weighted_volatility = 0.0

    for holding in holdings:
        key = (holding["exchange"], holding["symbol"].upper())
        quote = quotes.get(key, {})
        quantity = float(holding.get("quantity", 0))
        avg_cost = float(holding.get("avg_cost", 0))
        current_price = quote.get("close")
        cost_value = quantity * avg_cost
        current_value = quantity * current_price if current_price is not None else None
        unrealized = current_value - cost_value if current_value is not None else None
        change_pct = quote.get("change_pct")

        total_cost += cost_value
        if current_value is not None:
            total_value += current_value
        if current_value is not None and quote.get("previous_close") is not None:
            daily_pnl += quantity * (current_price - quote["previous_close"])

        # Constituent volatility is intentionally reported separately from
        # a true covariance-based portfolio volatility.
        rows = await db.eod_market_data.find(
            {"exchange": holding["exchange"], "symbol": holding["symbol"].upper()},
            {"_id": 0},
        ).sort("trade_date", -1).to_list(length=60)
        rows.reverse()
        records = []
        for row in rows:
            try:
                records.append(EODRecord.model_validate(row))
            except Exception:
                pass
        volatility = None
        if records:
            volatility = compute_technical_snapshot(records).annualized_volatility_pct

        enriched.append({
            "symbol": holding["symbol"].upper(),
            "exchange": holding["exchange"],
            "name": quote.get("name"),
            "quantity": quantity,
            "avg_cost": avg_cost,
            "cost_value": cost_value,
            "current_price": current_price,
            "current_value": current_value,
            "unrealized_pnl": unrealized,
            "change_pct": change_pct,
            "holding_volatility_pct": volatility,
            "data_status": quote.get("data_status", "missing"),
            "trade_date": quote.get("trade_date"),
        })

    unrealized_total = total_value - total_cost
    allocations = []
    for item in enriched:
        value = item["current_value"]
        allocation = (value / total_value * 100) if value is not None and total_value else None
        item["allocation_pct"] = allocation

    top_holding_pct = max(
        (item["allocation_pct"] for item in enriched if item["allocation_pct"] is not None),
        default=None,
    )

    for item in enriched:
        if item["allocation_pct"] is not None and item["holding_volatility_pct"] is not None:
            weighted_volatility += item["allocation_pct"] / 100 * item["holding_volatility_pct"]

    return {
        "portfolio_id": portfolio_id,
        "name": portfolio["name"],
        "benchmark": portfolio.get("benchmark"),
        "holdings": enriched,
        "summary": {
            "invested_cost": total_cost,
            "current_value": total_value,
            "unrealized_pnl": unrealized_total,
            "unrealized_pnl_pct": (unrealized_total / total_cost * 100) if total_cost else None,
            "daily_pnl": daily_pnl,
            "holdings_count": len(enriched),
            "top_holding_allocation_pct": top_holding_pct,
            "weighted_constituent_volatility_pct": weighted_volatility or None,
        },
        "allocation": sorted(
            [
                {
                    "symbol": item["symbol"],
                    "value": item["current_value"],
                    "allocation_pct": item["allocation_pct"],
                }
                for item in enriched
            ],
            key=lambda x: x["allocation_pct"] if x["allocation_pct"] is not None else -1,
            reverse=True,
        ),
        "sector_exposure": [],
        "benchmark_comparison": {
            "status": "missing",
            "message": "Dedicated benchmark index series is not currently ingested; no benchmark return is inferred."
        },
        "risk": {
            "weighted_constituent_volatility_pct": weighted_volatility or None,
            "concentration_pct": top_holding_pct,
            "method": "market-value-weighted constituent annualized volatility; covariance is not modeled",
        },
        "data_status": "eod" if enriched and any(x["current_price"] is not None for x in enriched) else "missing",
        "generated_at": datetime.now(timezone.utc),
    }
