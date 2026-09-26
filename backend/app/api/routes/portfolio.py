from __future__ import annotations

from datetime import datetime, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps.auth import get_current_user, require_permission
from app.db.mongo import get_database
from app.services.audit import record_audit
from app.services.portfolio import build_portfolio_snapshot
from app.services.portfolio_intelligence import build_portfolio_intelligence

router=APIRouter(prefix="/api/v1/portfolio",tags=["portfolio"])


class PortfolioCreate(BaseModel):
    name: str = Field(min_length=2,max_length=80)
    benchmark: str | None = Field(default=None,max_length=32)


class PortfolioUpdate(BaseModel):
    name: str | None = Field(default=None,min_length=2,max_length=80)
    benchmark: str | None = Field(default=None,max_length=32)


class TransactionCreate(BaseModel):
    symbol: str = Field(min_length=1,max_length=32)
    exchange: str = Field(default="NSE",pattern="^(NSE|BSE)$")
    side: str = Field(pattern="^(BUY|SELL)$")
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    fees: float = Field(default=0,ge=0)
    trade_date: str


@router.get("")
async def list_portfolios(current_user:dict=Depends(get_current_user)):
    rows=await get_database().portfolios.find({"user_id":current_user["user_id"]},{"_id":0}).sort("created_at",-1).to_list(length=100)
    return {"portfolios":rows}


@router.post("",status_code=201)
async def create_portfolio(payload:PortfolioCreate,current_user:dict=Depends(require_permission("portfolio.manage"))):
    db=get_database()
    if await db.portfolios.find_one({"user_id":current_user["user_id"],"name":payload.name}):
        raise HTTPException(409,"A portfolio with this name already exists")
    now=datetime.now(timezone.utc)
    portfolio={"portfolio_id":secrets.token_urlsafe(18),"user_id":current_user["user_id"],"name":payload.name,"benchmark":payload.benchmark.upper() if payload.benchmark else None,"created_at":now,"updated_at":now}
    await db.portfolios.insert_one(portfolio)
    await record_audit("portfolio.created",user_id=current_user["user_id"],target_type="portfolio",target_id=portfolio["portfolio_id"])
    return {k:v for k,v in portfolio.items() if k!="_id"}


@router.patch("/{portfolio_id}")
async def update_portfolio(portfolio_id:str,payload:PortfolioUpdate,current_user:dict=Depends(require_permission("portfolio.manage"))):
    db=get_database()
    portfolio=await db.portfolios.find_one({"portfolio_id":portfolio_id,"user_id":current_user["user_id"]})
    if not portfolio: raise HTTPException(404,"Portfolio not found")
    updates=payload.model_dump(exclude_none=True)
    if "benchmark" in updates and updates["benchmark"]:
        updates["benchmark"]=updates["benchmark"].upper()
    updates["updated_at"]=datetime.now(timezone.utc)
    await db.portfolios.update_one({"_id":portfolio["_id"]},{"$set":updates})
    return {"status":"updated","portfolio_id":portfolio_id}


@router.delete("/{portfolio_id}")
async def delete_portfolio(portfolio_id:str,current_user:dict=Depends(require_permission("portfolio.manage"))):
    db=get_database()
    portfolio=await db.portfolios.find_one({"portfolio_id":portfolio_id,"user_id":current_user["user_id"]})
    if not portfolio: raise HTTPException(404,"Portfolio not found")
    await db.portfolio_holdings.delete_many({"portfolio_id":portfolio_id,"user_id":current_user["user_id"]})
    await db.portfolio_transactions.delete_many({"portfolio_id":portfolio_id,"user_id":current_user["user_id"]})
    await db.portfolios.delete_one({"_id":portfolio["_id"]})
    await record_audit("portfolio.deleted",user_id=current_user["user_id"],target_type="portfolio",target_id=portfolio_id)
    return {"status":"deleted","portfolio_id":portfolio_id}


@router.get("/{portfolio_id}")
async def get_portfolio(portfolio_id:str,current_user:dict=Depends(get_current_user)):
    try: return await build_portfolio_snapshot(portfolio_id,current_user["user_id"])
    except ValueError as exc: raise HTTPException(404,str(exc)) from exc


@router.get("/{portfolio_id}/transactions")
async def list_transactions(portfolio_id:str,current_user:dict=Depends(get_current_user)):
    db=get_database()
    rows=await db.portfolio_transactions.find({"portfolio_id":portfolio_id,"user_id":current_user["user_id"]},{"_id":0}).sort("trade_date",-1).to_list(length=500)
    return {"transactions":rows}


@router.post("/{portfolio_id}/transactions",status_code=201)
async def add_transaction(portfolio_id:str,payload:TransactionCreate,current_user:dict=Depends(require_permission("portfolio.manage"))):
    db=get_database()
    portfolio=await db.portfolios.find_one({"portfolio_id":portfolio_id,"user_id":current_user["user_id"]})
    if not portfolio: raise HTTPException(404,"Portfolio not found")

    symbol=payload.symbol.upper(); exchange=payload.exchange
    now=datetime.now(timezone.utc)
    holding=await db.portfolio_holdings.find_one({"portfolio_id":portfolio_id,"user_id":current_user["user_id"],"symbol":symbol,"exchange":exchange})

    qty=payload.quantity
    if payload.side=="BUY":
        old_qty=float(holding.get("quantity",0)) if holding else 0
        old_avg=float(holding.get("avg_cost",0)) if holding else 0
        new_qty=old_qty+qty
        new_avg=((old_qty*old_avg)+(qty*payload.price)+payload.fees)/new_qty
        if holding:
            await db.portfolio_holdings.update_one({"_id":holding["_id"]},{"$set":{"quantity":new_qty,"avg_cost":new_avg,"updated_at":now}})
        else:
            await db.portfolio_holdings.insert_one({"holding_id":secrets.token_urlsafe(18),"portfolio_id":portfolio_id,"user_id":current_user["user_id"],"symbol":symbol,"exchange":exchange,"quantity":new_qty,"avg_cost":new_avg,"created_at":now,"updated_at":now})
    else:
        if not holding or float(holding.get("quantity",0))<qty:
            raise HTTPException(400,"Sell quantity exceeds current holding")
        new_qty=float(holding["quantity"])-qty
        if new_qty==0:
            await db.portfolio_holdings.delete_one({"_id":holding["_id"]})
        else:
            await db.portfolio_holdings.update_one({"_id":holding["_id"]},{"$set":{"quantity":new_qty,"updated_at":now}})

    tx={"transaction_id":secrets.token_urlsafe(18),"portfolio_id":portfolio_id,"user_id":current_user["user_id"],"symbol":symbol,"exchange":exchange,"side":payload.side,"quantity":qty,"price":payload.price,"fees":payload.fees,"trade_date":payload.trade_date,"created_at":now}
    await db.portfolio_transactions.insert_one(tx)
    await record_audit("portfolio.transaction_added",user_id=current_user["user_id"],target_type="portfolio",target_id=portfolio_id,metadata={"symbol":symbol,"side":payload.side,"quantity":qty})
    return {k:v for k,v in tx.items() if k!="_id"}


@router.get("/{portfolio_id}/risk")
async def portfolio_risk(portfolio_id:str,current_user:dict=Depends(get_current_user)):
    snapshot=await get_portfolio(portfolio_id,current_user)
    return {"portfolio_id":portfolio_id,"risk":snapshot["risk"],"concentration":snapshot["summary"]["top_holding_allocation_pct"],"data_status":snapshot["data_status"]}


@router.get("/{portfolio_id}/intelligence")
async def portfolio_intelligence(portfolio_id: str, current_user: dict = Depends(require_permission("analysis.basic"))):
    try:
        return await build_portfolio_intelligence(portfolio_id, current_user["user_id"])
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
