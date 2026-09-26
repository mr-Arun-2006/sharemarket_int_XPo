from dataclasses import dataclass

@dataclass(frozen=True)
class RegimeInput:
    index_return_pct: float
    breadth_pct: float
    volatility_pct: float
    volume_ratio: float

@dataclass(frozen=True)
class RegimeResult:
    label: str
    reasons: list[str]

def classify_regime(data: RegimeInput) -> RegimeResult:
    reasons: list[str] = []
    if data.index_return_pct >= 1.0 and data.breadth_pct >= 15:
        label = "Positive Momentum"
        reasons.extend(["Index return is positive", "Market breadth is supportive"])
    elif data.index_return_pct <= -1.0 and data.breadth_pct <= -15:
        label = "Broad Weakness"
        reasons.extend(["Index return is negative", "Market breadth is weak"])
    elif data.volatility_pct >= 2.5 or data.volume_ratio >= 1.8:
        label = "High Volatility"
        reasons.append("Volatility or participation is elevated")
    else:
        label = "Mixed / Range-bound"
        reasons.append("No strong broad-market regime signal detected")
    return RegimeResult(label=label, reasons=reasons)
