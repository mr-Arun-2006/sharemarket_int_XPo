from __future__ import annotations
from dataclasses import dataclass
from math import sqrt
from statistics import mean, pstdev
from app.schemas.market import EODRecord

@dataclass(frozen=True)
class TechnicalSnapshot:
    periods: int
    sma_5: float | None
    sma_20: float | None
    ema_5: float | None
    ema_20: float | None
    rsi_14: float | None
    macd: float | None
    macd_signal: float | None
    macd_histogram: float | None
    bollinger_middle_20: float | None
    bollinger_upper_20: float | None
    bollinger_lower_20: float | None
    bollinger_width_pct: float | None
    atr_14: float | None
    annualized_volatility_pct: float | None
    max_drawdown_pct: float | None
    volume_ratio_5: float | None

def _ema(values: list[float], period: int) -> float | None:
    if len(values) < period: return None
    k = 2 / (period + 1)
    value = sum(values[:period]) / period
    for item in values[period:]:
        value = item * k + value * (1 - k)
    return value

def _sma(values: list[float], period: int) -> float | None:
    return sum(values[-period:]) / period if len(values) >= period else None

def _rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period: return None
    gains=[]; losses=[]
    for prev, cur in zip(values[-(period+1):], values[-period:]):
        delta=cur-prev; gains.append(max(delta,0.0)); losses.append(max(-delta,0.0))
    avg_gain=sum(gains)/period; avg_loss=sum(losses)/period
    if avg_loss == 0: return 100.0 if avg_gain > 0 else 50.0
    rs=avg_gain/avg_loss
    return 100 - 100/(1+rs)

def _bollinger(values: list[float], period: int=20):
    if len(values) < period: return None,None,None,None
    window=values[-period:]; middle=mean(window); sigma=pstdev(window)
    upper=middle+2*sigma; lower=middle-2*sigma
    return middle,upper,lower,((upper-lower)/middle*100 if middle else None)

def _macd(values: list[float]):
    if len(values) < 35: return None,None,None
    series=[]
    for i in range(26, len(values)+1):
        fast=_ema(values[:i],12); slow=_ema(values[:i],26)
        if fast is not None and slow is not None: series.append(fast-slow)
    value=series[-1] if series else None; signal=_ema(series,9) if series else None
    return value,signal,(value-signal if value is not None and signal is not None else None)

def _atr(rows: list[EODRecord], period:int=14):
    trs=[]; prev=None
    for row in rows:
        if row.high is None or row.low is None: continue
        tr=row.high-row.low if prev is None else max(row.high-row.low,abs(row.high-prev),abs(row.low-prev))
        trs.append(max(tr,0.0))
        if row.close is not None: prev=row.close
    return sum(trs[-period:])/period if len(trs)>=period else None

def _annualized_volatility(values:list[float]):
    if len(values)<3: return None
    returns=[cur/prev-1 for prev,cur in zip(values,values[1:]) if prev]
    return pstdev(returns)*sqrt(252)*100 if len(returns)>=2 else None

def _max_drawdown(values:list[float]):
    if not values: return None
    peak=values[0]; drawdown=0.0
    for value in values:
        peak=max(peak,value)
        if peak: drawdown=min(drawdown,(value-peak)/peak*100)
    return drawdown

def compute_technical_snapshot(records:list[EODRecord]) -> TechnicalSnapshot:
    rows=sorted(records,key=lambda r:r.trade_date)
    closes=[r.close for r in rows if r.close is not None]
    volumes=[r.volume for r in rows if r.volume is not None]
    middle,upper,lower,width=_bollinger(closes,20)
    macd,signal,hist=_macd(closes)
    volume_ratio=None
    if len(volumes)>=6:
        baseline=mean(volumes[-6:-1])
        if baseline: volume_ratio=volumes[-1]/baseline
    return TechnicalSnapshot(
        periods=len(closes), sma_5=_sma(closes,5), sma_20=_sma(closes,20),
        ema_5=_ema(closes,5), ema_20=_ema(closes,20), rsi_14=_rsi(closes),
        macd=macd, macd_signal=signal, macd_histogram=hist,
        bollinger_middle_20=middle, bollinger_upper_20=upper, bollinger_lower_20=lower,
        bollinger_width_pct=width, atr_14=_atr(rows), annualized_volatility_pct=_annualized_volatility(closes),
        max_drawdown_pct=_max_drawdown(closes), volume_ratio_5=volume_ratio
    )
