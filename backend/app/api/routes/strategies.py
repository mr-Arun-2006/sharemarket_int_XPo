from __future__ import annotations

from datetime import datetime, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps.auth import get_current_user, require_permission
from app.db.mongo import get_database
from app.services.audit import record_audit
from app.services.backtest import run_sma_crossover

router=APIRouter(prefix="/api/v1/strategies",tags=["strategies"])


class StrategyCreate(BaseModel):
    name: str = Field(min_length=2,max_length=80)
    strategy_type: str = Field(default="sma_crossover",pattern="^sma_crossover$")
    fast_period: int = Field(default=10,ge=2,le=100)
    slow_period: int = Field(default=30,ge=3,le=250)


class BacktestRequest(BaseModel):
    symbol: str = Field(min_length=1,max_length=32)
    exchange: str = Field(default="NSE",pattern="^(NSE|BSE)$")
    fast_period: int = Field(default=10,ge=2,le=100)
    slow_period: int = Field(default=30,ge=3,le=250)
    initial_cash: float = Field(default=100000,gt=0)
    commission_bps: float = Field(default=5,ge=0,le=200)
    from_date: str | None = None
    to_date: str | None = None


@router.get("")
async def list_strategies(current_user:dict=Depends(get_current_user)):
    rows=await get_database().strategies.find({"user_id":current_user["user_id"]},{"_id":0}).sort("created_at",-1).to_list(length=100)
    return {"strategies":rows}


@router.post("",status_code=201)
async def create_strategy(payload:StrategyCreate,current_user:dict=Depends(require_permission("strategies.manage"))):
    if payload.fast_period>=payload.slow_period: raise HTTPException(400,"fast_period must be smaller than slow_period")
    now=datetime.now(timezone.utc)
    item={"strategy_id":secrets.token_urlsafe(18),"user_id":current_user["user_id"],"name":payload.name,"strategy_type":payload.strategy_type,"fast_period":payload.fast_period,"slow_period":payload.slow_period,"created_at":now,"updated_at":now}
    await get_database().strategies.insert_one(item)
    await record_audit("strategy.created",user_id=current_user["user_id"],target_type="strategy",target_id=item["strategy_id"])
    return {k:v for k,v in item.items() if k!="_id"}


@router.delete("/{strategy_id}")
async def delete_strategy(strategy_id:str,current_user:dict=Depends(require_permission("strategies.manage"))):
    result=await get_database().strategies.delete_one({"strategy_id":strategy_id,"user_id":current_user["user_id"]})
    if not result.deleted_count: raise HTTPException(404,"Strategy not found")
    return {"status":"deleted","strategy_id":strategy_id}


@router.post("/backtest")
async def run_backtest(payload:BacktestRequest,current_user:dict=Depends(require_permission("strategies.manage"))):
    try:
        result=await run_sma_crossover(
            symbol=payload.symbol,exchange=payload.exchange,fast_period=payload.fast_period,
            slow_period=payload.slow_period,initial_cash=payload.initial_cash,
            commission_bps=payload.commission_bps,from_date=payload.from_date,to_date=payload.to_date,
        )
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from exc

    backtest_id=secrets.token_urlsafe(18)
    document={
        "backtest_id":backtest_id,"user_id":current_user["user_id"],
        "strategy_type":"sma_crossover","parameters":payload.model_dump(),
        "result":result.__dict__,"created_at":datetime.now(timezone.utc),
    }
    await get_database().backtest_runs.insert_one(document)
    await record_audit("strategy.backtest_run",user_id=current_user["user_id"],target_type="backtest",target_id=backtest_id,metadata={"symbol":payload.symbol.upper()})
    return document | {"_id":None}


@router.get("/history")
async def backtest_history(limit:int=Query(default=50,ge=1,le=100),current_user:dict=Depends(get_current_user)):
    rows=await get_database().backtest_runs.find({"user_id":current_user["user_id"]},{"_id":0}).sort("created_at",-1).to_list(length=limit)
    return {"backtests":rows}
