from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

Exchange = Literal["NSE", "BSE"]
DataStatus = Literal["live", "eod", "latest_available", "missing", "stale"]

class MarketQuote(BaseModel):
    exchange: Exchange
    symbol: str = Field(min_length=1, max_length=32)
    name: str | None = None
    price: float | None = None
    previous_close: float | None = None
    change_pct: float | None = None
    volume: float | None = None
    data_status: DataStatus = "latest_available"
    as_of: datetime | None = None

class EODRecord(BaseModel):
    exchange: Exchange
    symbol: str
    trade_date: str
    name: str | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    previous_close: float | None = None
    volume: float | None = None
    turnover: float | None = None
    trades: int | None = None
    source_file: str | None = None
    source: str = "exchange"
