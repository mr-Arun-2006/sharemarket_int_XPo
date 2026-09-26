from fastapi import APIRouter, Depends, Query
from app.api.deps.auth import require_permission
from app.db.mongo import get_database

router=APIRouter(prefix="/api/v1/screener",tags=["screener"])

def _pct(close,previous):
    if close is None or previous in (None,0): return None
    return (close-previous)/previous*100

@router.get("/run")
async def run_screener(
    exchange:str=Query(default="NSE",pattern="^(?i:NSE|BSE)$"),
    min_change_pct:float|None=None,
    max_change_pct:float|None=None,
    min_volume:float|None=None,
    sort_by:str=Query(default="change_pct",pattern="^(?i:change_pct|volume|symbol)$"),
    limit:int=Query(default=50,ge=1,le=200),
    _:dict=Depends(require_permission("market.read")),
):
    exchange=exchange.upper(); sort_by=sort_by.lower(); db=get_database()
    latest=await db.eod_market_data.find_one({"exchange":exchange},{"_id":0,"trade_date":1},sort=[("trade_date",-1)])
    if not latest: return {"exchange":exchange,"trade_date":None,"count":0,"results":[]}
    docs=await db.eod_market_data.find({"exchange":exchange,"trade_date":latest["trade_date"]},{"_id":0,"symbol":1,"name":1,"close":1,"previous_close":1,"volume":1}).to_list(length=10000)
    results=[]
    for row in docs:
        change=_pct(row.get("close"),row.get("previous_close"))
        volume=row.get("volume")
        if change is None: continue
        if min_change_pct is not None and change<min_change_pct: continue
        if max_change_pct is not None and change>max_change_pct: continue
        if min_volume is not None and (volume is None or volume<min_volume): continue
        results.append({**row,"change_pct":change,"data_status":"eod","trade_date":latest["trade_date"]})
    if sort_by=="change_pct": results.sort(key=lambda x:x["change_pct"],reverse=True)
    elif sort_by=="volume": results.sort(key=lambda x:(x.get("volume") is not None,x.get("volume") or 0),reverse=True)
    else: results.sort(key=lambda x:x["symbol"])
    return {"exchange":exchange,"trade_date":latest["trade_date"],"count":len(results),"results":results[:limit]}
