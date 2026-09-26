from __future__ import annotations

from typing import Any

from app.services.portfolio import build_portfolio_snapshot


async def build_portfolio_intelligence(portfolio_id: str, user_id: str) -> dict[str, Any]:
    snapshot = await build_portfolio_snapshot(portfolio_id, user_id)
    summary = snapshot["summary"]
    holdings = snapshot["holdings"]

    reasons: list[str] = []
    if summary["unrealized_pnl_pct"] is not None:
        if summary["unrealized_pnl_pct"] > 0:
            reasons.append("The portfolio is above aggregate recorded cost basis on the latest available EOD prices.")
        elif summary["unrealized_pnl_pct"] < 0:
            reasons.append("The portfolio is below aggregate recorded cost basis on the latest available EOD prices.")
        else:
            reasons.append("The portfolio is approximately at aggregate recorded cost basis on the latest available EOD prices.")

    concentration = summary["top_holding_allocation_pct"]
    if concentration is not None:
        reasons.append(f"The largest holding represents {concentration:.2f}% of current portfolio value.")

    with_prices = [h for h in holdings if h["current_price"] is not None]
    missing_prices = [h["symbol"] for h in holdings if h["current_price"] is None]
    if missing_prices:
        reasons.append("Current EOD price data is unavailable for: " + ", ".join(missing_prices[:10]) + ".")

    return {
        "portfolio_id": portfolio_id,
        "data_status": snapshot["data_status"],
        "diagnosis": "Portfolio context available",
        "summary": {
            "invested_cost": summary["invested_cost"],
            "current_value": summary["current_value"],
            "unrealized_pnl": summary["unrealized_pnl"],
            "unrealized_pnl_pct": summary["unrealized_pnl_pct"],
            "daily_pnl": summary["daily_pnl"],
            "holdings_count": summary["holdings_count"],
        },
        "key_observations": reasons,
        "risk_observations": [
            f"Top holding concentration: {concentration:.2f}%." if concentration is not None else "Concentration cannot be calculated from current data.",
            (
                f"Weighted constituent volatility: {summary['weighted_constituent_volatility_pct']:.2f}%."
                if summary["weighted_constituent_volatility_pct"] is not None
                else "Volatility cannot be calculated from current constituent history."
            ),
        ],
        "data_gaps": [
            "Sector exposure is unavailable because sector classification is not yet stored with portfolio holdings.",
            "Benchmark comparison is unavailable because a dedicated benchmark index series is not yet ingested.",
        ] + (["Some holdings do not have current EOD prices."] if missing_prices else []),
        "coverage": {
            "holdings_with_price": len(with_prices),
            "holdings_without_price": len(missing_prices),
        },
        "method": "Private deterministic portfolio analysis. No private portfolio data is sent to the external AI provider.",
    }
