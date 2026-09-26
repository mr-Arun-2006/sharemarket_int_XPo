from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Iterable
from app.schemas.market import EODRecord
from app.services.regime import RegimeInput, RegimeResult, classify_regime

@dataclass(frozen=True)
class StockSnapshot:
    exchange:str; symbol:str; name:str|None; close:float|None; previous_close:float|None
    change_pct:float|None; volume:float|None; volume_ratio:float|None; volatility_pct:float|None

@dataclass(frozen=True)
class EODMarketSummary:
    trade_date:str; nse_stocks:int; nse_positive:int; nse_negative:int; nse_unchanged:int
    nse_breadth_pct:float|None; nse_mean_change_pct:float|None
    top_gainers:list[StockSnapshot]; top_losers:list[StockSnapshot]; top_volume:list[StockSnapshot]
    regime:RegimeResult

def _pct_change(close,previous):
    return None if close is None or previous in (None,0) else (close-previous)/previous*100

def _history(records):
    h=defaultdict(list)
    for r in records: h[(r.exchange,r.symbol)].append(r)
    for values in h.values(): values.sort(key=lambda x:x.trade_date)
    return h

def _snapshot(history,current):
    change=_pct_change(current.close,current.previous_close)
    prior=[r.volume for r in history if r.trade_date<current.trade_date and r.volume is not None][-5:]
    baseline=mean(prior) if prior else None
    ratio=(current.volume/baseline) if current.volume is not None and baseline else None
    closes=[r.close for r in history[-5:] if r.close is not None]
    returns=[(b-a)/a*100 for a,b in zip(closes,closes[1:]) if a]
    return StockSnapshot(current.exchange,current.symbol,current.name,current.close,current.previous_close,change,current.volume,ratio,pstdev(returns) if len(returns)>=2 else None)

def build_market_summary(records:Iterable[EODRecord],trade_date:str|None=None)->EODMarketSummary:
    rows=[r for r in records if r.exchange=="NSE"]
    if not rows: raise ValueError("No NSE EOD records available")
    dates=sorted({r.trade_date for r in rows})
    day=trade_date or dates[-1]
    current=[r for r in rows if r.trade_date==day]
    if not current: raise ValueError("No NSE EOD records for requested trade date")
    history=_history(rows)
    snapshots=[_snapshot(history[(r.exchange,r.symbol)],r) for r in current]
    usable=[s for s in snapshots if s.change_pct is not None]
    positive=sum(1 for s in usable if s.change_pct>0); negative=sum(1 for s in usable if s.change_pct<0)
    breadth=(positive-negative)/len(usable)*100 if usable else None
    mean_change=mean([s.change_pct for s in usable]) if usable else None
    vol=mean([s.volatility_pct for s in snapshots if s.volatility_pct is not None]) if any(s.volatility_pct is not None for s in snapshots) else 0
    vr=mean([s.volume_ratio for s in snapshots if s.volume_ratio is not None]) if any(s.volume_ratio is not None for s in snapshots) else 0
    regime=classify_regime(RegimeInput(mean_change or 0,breadth or 0,vol,vr))
    gainers=sorted([s for s in usable if s.change_pct>0],key=lambda s:s.change_pct,reverse=True)[:10]
    losers=sorted([s for s in usable if s.change_pct<0],key=lambda s:s.change_pct)[:10]
    top_volume=sorted(snapshots,key=lambda s:s.volume_ratio or 0,reverse=True)[:10]
    return EODMarketSummary(day,len(snapshots),positive,negative,len(usable)-positive-negative,breadth,mean_change,gainers,losers,top_volume,regime)
