"use client";

import { FormEvent, useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { apiFetch } from "../../lib/api";

type Portfolio={portfolio_id:string;name:string;benchmark?:string|null};
type Holding={symbol:string;exchange:string;name?:string|null;quantity:number;avg_cost:number;cost_value:number;current_price:number|null;current_value:number|null;unrealized_pnl:number|null;change_pct:number|null;allocation_pct:number|null;data_status:string};
type Snapshot={portfolio_id:string;name:string;benchmark?:string|null;holdings:Holding[];summary:{invested_cost:number;current_value:number;unrealized_pnl:number;unrealized_pnl_pct:number|null;daily_pnl:number;holdings_count:number;top_holding_allocation_pct:number|null;weighted_constituent_volatility_pct:number|null};allocation:{symbol:string;value:number|null;allocation_pct:number|null}[];sector_exposure:unknown[];benchmark_comparison:{status:string;message:string};risk:{weighted_constituent_volatility_pct:number|null;concentration_pct:number|null;method:string};data_status:string};

export default function PortfolioPage(){
  const [portfolios,setPortfolios]=useState<Portfolio[]>([]); const [selected,setSelected]=useState(""); const [data,setData]=useState<Snapshot|null>(null);
  const [name,setName]=useState(""); const [symbol,setSymbol]=useState(""); const [qty,setQty]=useState(""); const [price,setPrice]=useState(""); const [side,setSide]=useState("BUY"); const [date,setDate]=useState(new Date().toISOString().slice(0,10));
  const [error,setError]=useState(""); const [message,setMessage]=useState("");

  async function loadPortfolios(){
    try{const r=await apiFetch<{portfolios:Portfolio[]}>("/api/v1/portfolio");setPortfolios(r.portfolios);if(!selected&&r.portfolios[0])setSelected(r.portfolios[0].portfolio_id);}
    catch(e){setError(e instanceof Error?e.message:"Unable to load portfolios");}
  }
  async function loadSnapshot(id=selected){
    if(!id)return;
    try{setData(await apiFetch<Snapshot>("/api/v1/portfolio/"+encodeURIComponent(id)));}
    catch(e){setError(e instanceof Error?e.message:"Unable to load portfolio");}
  }
  useEffect(()=>{loadPortfolios()},[]);
  useEffect(()=>{if(selected)loadSnapshot(selected)},[selected]);

  async function createPortfolio(e:FormEvent){
    e.preventDefault();setError("");setMessage("");
    try{const r=await apiFetch<Portfolio>("/api/v1/portfolio",{method:"POST",body:JSON.stringify({name})});setName("");setSelected(r.portfolio_id);await loadPortfolios();await loadSnapshot(r.portfolio_id);setMessage("Portfolio created.");}
    catch(err){setError(err instanceof Error?err.message:"Unable to create portfolio");}
  }
  async function addTransaction(e:FormEvent){
    e.preventDefault();setError("");setMessage("");
    if(!selected)return;
    try{
      await apiFetch("/api/v1/portfolio/"+selected+"/transactions",{method:"POST",body:JSON.stringify({symbol:symbol.toUpperCase(),exchange:"NSE",side,quantity:Number(qty),price:Number(price),fees:0,trade_date:date})});
      setSymbol("");setQty("");setPrice("");setMessage("Transaction recorded.");await loadSnapshot();
    }catch(err){setError(err instanceof Error?err.message:"Unable to record transaction");}
  }

  const money=(v:number|null|undefined)=>v==null?"--":v.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
  const pct=(v:number|null|undefined)=>v==null?"--":v.toFixed(2)+"%";

  return <AppShell>
    <section className="page-heading"><div><div className="eyebrow">Portfolio</div><h1>Portfolio intelligence</h1><p className="lead">Private holdings, transaction-based cost basis, EOD valuation, allocation and risk context.</p></div></section>
    {error&&<div className="error">{error}</div>}{message&&<div className="panel" style={{marginBottom:18}}>{message}</div>}

    <section className="grid-2">
      <article className="panel"><div className="eyebrow">Portfolio</div><h2>Create portfolio</h2><form onSubmit={createPortfolio}><input value={name} onChange={e=>setName(e.target.value)} placeholder="Portfolio name" required/><div className="actions"><button className="button primary">Create</button></div></form></article>
      <article className="panel"><div className="eyebrow">Workspace</div><h2>Select portfolio</h2><select value={selected} onChange={e=>setSelected(e.target.value)}>{portfolios.map(p=><option key={p.portfolio_id} value={p.portfolio_id}>{p.name}</option>)}</select></article>
    </section>

    {selected&&<section className="panel" style={{marginTop:18}}><div className="eyebrow">Transaction</div><h2>Add BUY / SELL</h2><form onSubmit={addTransaction}><div className="grid-2"><input value={symbol} onChange={e=>setSymbol(e.target.value)} placeholder="NSE symbol" required/><select value={side} onChange={e=>setSide(e.target.value)}><option>BUY</option><option>SELL</option></select><input value={qty} onChange={e=>setQty(e.target.value)} type="number" min="0.0001" step="any" placeholder="Quantity" required/><input value={price} onChange={e=>setPrice(e.target.value)} type="number" min="0.01" step="any" placeholder="Execution price" required/><input value={date} onChange={e=>setDate(e.target.value)} type="date" required/></div><div className="actions"><button className="button primary">Record Transaction</button></div></form></section>}

    {data&&<><section className="metric-grid" style={{marginTop:18}}>
      <article className="panel"><div className="eyebrow">Current Value</div><div className="metric">₹{money(data.summary.current_value)}</div><div className="caption">EOD valuation · {data.data_status}</div></article>
      <article className="panel"><div className="eyebrow">Unrealized P&amp;L</div><div className="metric">₹{money(data.summary.unrealized_pnl)}</div><div className="caption">{pct(data.summary.unrealized_pnl_pct)} vs invested cost</div></article>
      <article className="panel"><div className="eyebrow">Daily P&amp;L</div><div className="metric">₹{money(data.summary.daily_pnl)}</div><div className="caption">Based on latest EOD previous close</div></article>
      <article className="panel"><div className="eyebrow">Concentration</div><div className="metric">{pct(data.summary.top_holding_allocation_pct)}</div><div className="caption">Largest holding allocation</div></article>
    </section>
    <section className="panel" style={{marginTop:18}}><div className="section-title"><div><div className="eyebrow">Holdings</div><h2>{data.name}</h2></div><span className="caption">{data.summary.holdings_count} holdings</span></div>
      <div className="table-wrap"><table><thead><tr><th>Symbol</th><th>Qty</th><th>Avg Cost</th><th>Price</th><th>Value</th><th>P&amp;L</th><th>Allocation</th><th>Data</th></tr></thead><tbody>{data.holdings.map(h=><tr key={h.exchange+h.symbol}><td>{h.symbol}</td><td>{h.quantity}</td><td>₹{money(h.avg_cost)}</td><td>{h.current_price==null?"--":"₹"+money(h.current_price)}</td><td>{h.current_value==null?"--":"₹"+money(h.current_value)}</td><td>{h.unrealized_pnl==null?"--":"₹"+money(h.unrealized_pnl)}</td><td>{pct(h.allocation_pct)}</td><td>{h.data_status}</td></tr>)}</tbody></table></div>
    </section>
    <section className="analysis-grid" style={{marginTop:18}}>
      <article className="panel"><div className="eyebrow">Risk</div><h2>Portfolio risk context</h2><div className="stats-row"><span>Weighted volatility: {pct(data.risk.weighted_constituent_volatility_pct)}</span><span>Concentration: {pct(data.risk.concentration_pct)}</span></div><p className="muted" style={{marginTop:12}}>{data.risk.method}</p></article>
      <article className="panel"><div className="eyebrow">Benchmark</div><h2>Benchmark comparison</h2><p className="muted">{data.benchmark_comparison.message}</p></article>
      <article className="panel full"><div className="eyebrow">Allocation</div><div className="table-wrap"><table><thead><tr><th>Symbol</th><th>Value</th><th>Allocation</th></tr></thead><tbody>{data.allocation.map(a=><tr key={a.symbol}><td>{a.symbol}</td><td>{a.value==null?"--":"₹"+money(a.value)}</td><td>{pct(a.allocation_pct)}</td></tr>)}</tbody></table></div></article>
    </section></>}
  </AppShell>
}
