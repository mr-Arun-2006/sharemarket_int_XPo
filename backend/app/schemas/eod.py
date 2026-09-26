from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

class EODAnalysisRequest(BaseModel):
    symbol: str | None = Field(default=None, max_length=32)
    trade_date: str | None = None
    language: str = "English"

class EODAnalysisResponse(BaseModel):
    analysis_id: str
    analysis_type: Literal["market", "stock"]
    status: Literal["complete", "partial", "unavailable"]
    trade_date: str
    generated_at: datetime
    executive_summary: str
    diagnosis: str
    market_metrics: dict
    regime: dict
    evidence: list[dict]
    disclaimer: str
