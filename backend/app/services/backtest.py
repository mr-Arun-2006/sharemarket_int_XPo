from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import Any

from app.db.mongo import get_database


@dataclass
class BacktestResult:
    symbol: str
    exchange: str
    from_date: str
    to_date: str
    initial_cash: float
    final_equity: float
    total_return_pct: float
    buy_hold_return_pct: float | None
    max_drawdown_pct: float
    trades: int
    wins: int
    losses: int
    equity_curve: list[dict[str, Any]]


async def load_price_rows(symbol: str, exchange: str, from_date: str | None, to_date: str | None):
    query: dict[str, Any] = {"symbol": symbol.upper(), "exchange": exchange}
    if from_date or to_date:
        query["trade_date"] = {}
        if from_date: query["trade_date"]["$gte"] = from_date
        if to_date: query["trade_date"]["$lte"] = to_date
    rows = await get_database().eod_market_data.find(
        query,
        {"_id": 0, "trade_date": 1, "open": 1, "close": 1},
    ).sort("trade_date", 1).to_list(length=1000)
    return [row for row in rows if row.get("open") is not None and row.get("close") is not None]


def _sma(values: list[float], period: int) -> float | None:
    return sum(values[-period:]) / period if len(values) >= period else None


async def run_sma_crossover(
    symbol: str,
    exchange: str,
    fast_period: int,
    slow_period: int,
    initial_cash: float,
    commission_bps: float = 5.0,
    from_date: str | None = None,
    to_date: str | None = None,
) -> BacktestResult:
    if fast_period >= slow_period:
        raise ValueError("fast_period must be smaller than slow_period")
    rows = await load_price_rows(symbol, exchange, from_date, to_date)
    if len(rows) < slow_period + 2:
        raise ValueError(f"At least {slow_period + 2} valid sessions are required")

    cash = float(initial_cash)
    shares = 0.0
    entry_price: float | None = None
    wins = losses = trades = 0
    curve = []

    for i in range(1, len(rows)):
        prior_closes = [float(r["close"]) for r in rows[:i]]
        fast_prev = _sma(prior_closes, fast_period)
        slow_prev = _sma(prior_closes, slow_period)
        current_closes = prior_closes + [float(rows[i]["close"])]
        fast_now = _sma(current_closes, fast_period)
        slow_now = _sma(current_closes, slow_period)

        if fast_prev is None or slow_prev is None or fast_now is None or slow_now is None:
            equity = cash + shares * float(rows[i]["close"])
            curve.append({"trade_date": rows[i]["trade_date"], "equity": equity})
            continue

        cross_up = fast_prev <= slow_prev and fast_now > slow_now
        cross_down = fast_prev >= slow_prev and fast_now < slow_now
        execution_price = float(rows[i]["open"])
        fee_rate = commission_bps / 10000.0

        if cross_up and shares == 0 and cash > 0:
            fees = cash * fee_rate
            shares = (cash - fees) / execution_price
            cash = 0.0
            entry_price = execution_price
            trades += 1
        elif cross_down and shares > 0:
            proceeds = shares * execution_price
            cash = proceeds - proceeds * fee_rate
            if entry_price is not None:
                if execution_price > entry_price:
                    wins += 1
                else:
                    losses += 1
            shares = 0.0
            entry_price = None

        equity = cash + shares * float(rows[i]["close"])
        curve.append({"trade_date": rows[i]["trade_date"], "equity": equity})

    if shares > 0:
        execution_price = float(rows[-1]["close"])
        proceeds = shares * execution_price
        cash = proceeds - proceeds * (commission_bps / 10000.0)
        if entry_price is not None:
            if execution_price > entry_price: wins += 1
            else: losses += 1
        shares = 0.0

    final_equity = cash
    peak = initial_cash
    max_drawdown = 0.0
    for point in curve:
        peak = max(peak, point["equity"])
        if peak:
            max_drawdown = min(max_drawdown, (point["equity"] - peak) / peak * 100)
    if curve:
        curve[-1]["equity"] = final_equity

    buy_hold = None
    first_close = float(rows[0]["close"])
    last_close = float(rows[-1]["close"])
    if first_close:
        buy_hold = (last_close / first_close - 1) * 100

    total_return = (final_equity / initial_cash - 1) * 100 if initial_cash else 0.0
    return BacktestResult(
        symbol=symbol.upper(),
        exchange=exchange,
        from_date=rows[0]["trade_date"],
        to_date=rows[-1]["trade_date"],
        initial_cash=initial_cash,
        final_equity=final_equity,
        total_return_pct=total_return,
        buy_hold_return_pct=buy_hold,
        max_drawdown_pct=max_drawdown,
        trades=trades,
        wins=wins,
        losses=losses,
        equity_curve=curve,
    )
