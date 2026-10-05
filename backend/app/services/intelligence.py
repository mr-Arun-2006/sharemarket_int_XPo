from __future__ import annotations

from typing import Any

from app.services.eod_engine import EODMarketSummary
from app.services.technical import compute_technical_snapshot
from app.services.fundamentals import get_fundamental_snapshot
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


async def build_ai_diagnosis(
    summary: EODMarketSummary,
    records: list[EODRecord],
    language: str = "en",
    symbol: str | None = None,
    context: dict[str, Any] | None = None,
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

    context = context or {}

    sectors_ctx = context.get("sectors", [])
    institutional_ctx = context.get("institutional_activity", [])
    events_ctx = context.get("major_events", [])

    if sectors_ctx:
        key_reasons.append("Leading sector by average move: " + str(sectors_ctx[0].get("sector")) + " (" + _fmt(sectors_ctx[0].get("average_change_pct")) + "%).")
        key_reasons.append("Weakest sector by average move: " + str(sectors_ctx[-1].get("sector")) + " (" + _fmt(sectors_ctx[-1].get("average_change_pct")) + "%).")
    for row in institutional_ctx:
        if row.get("net_value") is not None:
            key_reasons.append(str(row.get("category", "Institutional")) + " net value: " + _fmt(row.get("net_value")) + ".")
    if events_ctx:
        key_reasons.append(str(len(events_ctx)) + " exchange/company event records are available for the trade date.")

    sections: dict[str, Any] = {
        "market": {
            "status": "available",
            "diagnosis": summary.regime.label,
            "summary": _translation_prefix(language),
            "key_reasons": key_reasons,
        },
        "sectors": {
            "status": "available" if context.get("sectors") else "missing",
            "diagnosis": "Sector breadth available" if context.get("sectors") else None,
            "summary": ("Sector-level aggregates are derived from the current NSE EOD rows and stored sector mapping." if context.get("sectors") else "Sector classification data was not present; no sector conclusion is generated."),
            "leaders": context.get("sectors", [])[:8],
            "evidence": [{"id": "EV-SECTOR-COVERAGE", "type": "derived", "label": "Sector coverage", "value": context.get("sector_coverage", {}), "source": "sector_data mapping joined with NSE EOD dataset"}] if context.get("sectors") else [],
        },
        "institutional_activity": {
            "status": "available" if context.get("institutional_activity") else "missing",
            "diagnosis": "Institutional activity available" if context.get("institutional_activity") else None,
            "summary": ("FII/FPI and DII activity is shown from the ingested institutional dataset. Values are treated as source data, not forecasts." if context.get("institutional_activity") else "Institutional-flow data was not present; no institutional conclusion is generated."),
            "rows": context.get("institutional_activity", []),
            "evidence": [{"id": "EV-INSTITUTIONAL", "type": "source_data", "label": "Institutional activity", "value": context.get("institutional_activity", []), "source": "institutional_activity dataset"}] if context.get("institutional_activity") else [],
        },
        "major_events": {
            "status": "available" if context.get("major_events") else "missing",
            "diagnosis": "Corporate/event evidence available" if context.get("major_events") else None,
            "summary": ("Exchange/company event records are available for the selected trade date. Event text is displayed as source evidence." if context.get("major_events") else "Event/news evidence was not ingested; no event is inferred from price action alone."),
            "items": context.get("major_events", [])[:25],
            "evidence": [{"id": "EV-MARKET-EVENTS", "type": "source_data", "label": "Corporate/event records", "value": context.get("major_events", [])[:25], "source": "market_events dataset"}] if context.get("major_events") else [],
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
        # Fundamental data is source-backed and may be missing for the selected symbol.
        fundamentals = await get_fundamental_snapshot(symbol_upper, latest.trade_date)
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
            "fundamentals": fundamentals,
            "fundamentals_status": "available" if fundamentals else "missing",
        }
        evidence.extend(stock_evidence)
        if fundamentals:
            evidence.append({
                "id": "EV-STOCK-FUNDAMENTALS",
                "type": "fundamental_data",
                "label": f"{symbol_upper} fundamental snapshot",
                "value": fundamentals,
                "source": fundamentals.get("source_url") or fundamentals.get("source") or "fundamental_data dataset",
            })

    return {
        "language": language,
        "sections": sections,
        "evidence": evidence,
        "uncertainty": [
            "Any sector, institutional, event/news or dedicated-index field not present in the supplied dataset is explicitly excluded from conclusions.",
            "Derived indicators are based only on the sessions available in the ingested dataset.",
        ],
    }
