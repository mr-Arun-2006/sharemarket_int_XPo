from __future__ import annotations

from statistics import mean
from typing import Any

from app.services.eod_engine import EODMarketSummary
from app.services.technical import compute_technical_snapshot
from app.schemas.market import EODRecord


SUPPORTED_LANGUAGES = {"en": "English", "ta": "Tamil", "hi": "Hindi", "gu": "Gujarati", "kn": "Kannada"}


def _fmt(value: float | None, digits: int = 2) -> str:
    return "--" if value is None else f"{value:.{digits}f}"


def _stock_change(record: EODRecord) -> float | None:
    if record.close is None or record.previous_close in (None, 0):
        return None
    return (record.close - record.previous_close) / record.previous_close * 100


def _translation_prefix(language: str) -> str:
    if language == "ta":
        return "முக்கிய சந்தை ஆதாரங்கள் தமிழில் விளக்கப்படுகின்றன; financial terminology remains in English."
    if language == "hi":
        return "मुख्य बाजार साक्ष्य हिंदी में समझाए गए हैं; financial terminology remains in English."
    if language == "gu":
        return "મુખ્ય બજાર પુરાવા ગુજરાતીમાં સમજાવવામાં આવ્યા છે; financial terminology remains in English."
    if language == "kn":
        return "ಮುಖ್ಯ ಮಾರುಕಟ್ಟೆ ಸಾಕ್ಷ್ಯವನ್ನು ಕನ್ನಡದಲ್ಲಿ ವಿವರಿಸಲಾಗಿದೆ; financial terminology remains in English."
    return "Market evidence is explained in English; financial terminology is kept in English."


def build_ai_diagnosis(
    summary: EODMarketSummary,
    records: list[EODRecord],
    language: str = "en",
    symbol: str | None = None,
) -> dict[str, Any]:
    language = language if language in SUPPORTED_LANGUAGES else "en"
    evidence: list[dict[str, Any]] = [
        {
            "id": "EV-MKT-BREADTH",
            "type": "market_data",
            "label": "NSE breadth",
            "value": {
                "positive": summary.nse_positive,
                "negative": summary.nse_negative,
                "unchanged": summary.nse_unchanged,
                "breadth_pct": summary.nse_breadth_pct,
            },
            "source": "NSE EOD dataset stored in eod_market_data",
        },
        {
            "id": "EV-MKT-MEAN-MOVE",
            "type": "market_data",
            "label": "NSE average stock move",
            "value": summary.nse_mean_change_pct,
            "source": "NSE EOD dataset stored in eod_market_data",
        },
        {
            "id": "EV-REGIME",
            "type": "derived",
            "label": "Deterministic market regime",
            "value": summary.regime.label,
            "source": "rule-based regime engine",
        },
    ]

    key_reasons = list(summary.regime.reasons)
    if summary.top_gainers:
        key_reasons.append(f"Top observed gainer: {summary.top_gainers[0].symbol} ({_fmt(summary.top_gainers[0].change_pct)}%).")
    if summary.top_losers:
        key_reasons.append(f"Top observed loser: {summary.top_losers[0].symbol} ({_fmt(summary.top_losers[0].change_pct)}%).")

    sections: dict[str, Any] = {
        "market": {
            "status": "available",
            "diagnosis": summary.regime.label,
            "summary": _translation_prefix(language),
            "key_reasons": key_reasons,
        },
        "sectors": {
            "status": "missing",
            "diagnosis": None,
            "summary": "Sector classification data was not present in the ingested EOD dataset; no sector conclusion is generated.",
            "evidence": [],
        },
        "institutional_activity": {
            "status": "missing",
            "diagnosis": None,
            "summary": "FII/DII or equivalent institutional-flow data was not present in the current dataset; no institutional conclusion is generated.",
            "evidence": [],
        },
        "major_events": {
            "status": "missing",
            "diagnosis": None,
            "summary": "Event/news evidence is not part of the current EOD ingestion payload; no event is inferred from price action alone.",
            "evidence": [],
        },
    }

    if symbol:
        symbol_upper = symbol.upper()
        matches = [r for r in records if r.exchange == "NSE" and r.symbol.upper() == symbol_upper]
        if not matches:
            raise ValueError(f"No NSE EOD data found for {symbol_upper}")
        matches.sort(key=lambda r: r.trade_date)
        technical = compute_technical_snapshot(matches)
        latest = matches[-1]
        selected_change = _stock_change(latest)
        stock_evidence = [
            {
                "id": "EV-STOCK-LATEST",
                "type": "stock_data",
                "label": f"{symbol_upper} latest EOD",
                "value": {
                    "trade_date": latest.trade_date,
                    "close": latest.close,
                    "previous_close": latest.previous_close,
                    "change_pct": selected_change,
                    "volume": latest.volume,
                },
                "source": "NSE EOD dataset stored in eod_market_data",
            },
            {
                "id": "EV-STOCK-TECHNICAL",
                "type": "derived",
                "label": f"{symbol_upper} technical snapshot",
                "value": {
                    "rsi_14": technical.rsi_14,
                    "sma_20": technical.sma_20,
                    "ema_20": technical.ema_20,
                    "macd": technical.macd,
                    "macd_histogram": technical.macd_histogram,
                    "annualized_volatility_pct": technical.annualized_volatility_pct,
                },
                "source": "rule-based technical indicator engine",
            },
        ]
        stock_reasons = []
        if technical.rsi_14 is not None:
            if technical.rsi_14 >= 70:
                stock_reasons.append("RSI 14 is above the conventional 70 threshold.")
            elif technical.rsi_14 <= 30:
                stock_reasons.append("RSI 14 is below the conventional 30 threshold.")
            else:
                stock_reasons.append("RSI 14 is not in the conventional overbought/oversold zones.")
        if latest.close is not None and technical.sma_20 is not None:
            stock_reasons.append("Latest close is above SMA 20." if latest.close > technical.sma_20 else "Latest close is below SMA 20.")
        if technical.macd_histogram is not None:
            stock_reasons.append("MACD histogram is positive." if technical.macd_histogram > 0 else "MACD histogram is negative.")
        sections["selected_stock"] = {
            "status": "available",
            "symbol": symbol_upper,
            "diagnosis": "Technical context available",
            "summary": _translation_prefix(language),
            "key_reasons": stock_reasons,
            "latest": {
                "trade_date": latest.trade_date,
                "close": latest.close,
                "change_pct": selected_change,
            },
            "technical": technical.__dict__,
        }
        evidence.extend(stock_evidence)

    return {
        "language": language,
        "sections": sections,
        "evidence": evidence,
        "uncertainty": [
            "Missing sector, institutional-flow, event/news and dedicated index data are explicitly excluded from conclusions.",
            "Derived indicators are based only on the sessions available in the ingested dataset.",
        ],
    }
