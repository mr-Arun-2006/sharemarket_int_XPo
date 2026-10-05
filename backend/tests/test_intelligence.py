import asyncio
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

from app.schemas.market import EODRecord
from app.services.eod_engine import build_market_summary
from app.services.intelligence import build_ai_diagnosis


def test_stock_intelligence_loads_fundamentals():
    start = date(2026, 9, 1)
    records = [
        EODRecord(
            exchange="NSE",
            symbol="RELIANCE",
            trade_date=(start + timedelta(days=i)).isoformat(),
            close=100 + i,
            previous_close=99 + i,
            high=101 + i,
            low=98 + i,
            volume=1000 + (i * 10),
        )
        for i in range(20)
    ]
    summary = build_market_summary(records)

    with patch(
        "app.services.intelligence.get_fundamental_snapshot",
        new=AsyncMock(
            return_value={
                "symbol": "RELIANCE",
                "as_of": records[-1].trade_date,
                "pe": 25.0,
            }
        ),
    ):
        result = asyncio.run(
            build_ai_diagnosis(summary, records, symbol="RELIANCE")
        )

    assert result["sections"]["selected_stock"]["fundamentals"]["pe"] == 25.0
