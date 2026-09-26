"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "../../../components/AppShell";
import { apiFetch } from "../../../lib/api";

type Portfolio={portfolio_id:string;name:string};
type Intelligence={portfolio_id:string;data_status:string;diagnosis:string;summary:{invested_cost:number;current_value:number;unrealized_pnl:number;unrealized_pnl_pct:number|null;daily_pnl:number;holdings_count:number};key_observations:string[];risk_observations:string[];data_gaps:string[];coverage:{holdings_with_price:number;holdings_without_price:number};method:string};

export default function AIPortfolioPage(){
  const [portfolios,setPortfolios]=useState<Portfolio[]>([]); const [id,setId]=useState(""); const [data,setData]=useState<Intelligence|null>(null); const [error,setError]=useState(""); const [loading,setLoading]=useState(false);
  useEffect(()=>{apiFetch<{portfolios:Portfolio[]}>("/api/v1/portfolio").then(r=>{setPortfolios(r.portfolios);if(r.portfolios[0])setId(r.portfolios[0].portfolio_id)}).catch(e=>setError(e instanceof Error?e.message:"Unable to load portfolios"));},[]);
  async function generate(){if(!id)return;setLoading(true);setError("");try{setData(await apiFetch<Intelligence>("/api/v1/portfolio/"+encodeURIComponent(id)+"/intelligence"));}catch(e){setError(e instanceof Error?e.message:"Unable to generate portfolio intelligence");}finally{setLoading(false);}}
  const money=(v:number)=>v.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
  const pct=(v:number|null)=>v==null?"--":v.toFixed(2)+"%";
  return <AppShell><section className="page-heading"><div><div className="eyebrow">AI Intelligence / Portfolio</div><h1>Portfolio intelligence</h1><p className="lead">Private deterministic analysis of holdings, valuation, concentration and constituent risk. Private portfolio data is not sent to the external AI provider.</p></div></section>
    <section className="panel"><div className="actions"><select value={id} onChange={e=>setId(e.target.value)}>{portfolios.map(p=><option key={p.portfolio_id} value={p.portfolio_id}>{p.name}</option>)}</select><button className="button primary" onClick={generate} disabled={loading}>{loading?"Analysing...":"Analyse Portfolio"}</button><Link className="button" href="/portfolio">Open Portfolio</Link></div>{error&&<div className="error">{error}</div>}</section>
    {data&&<section className="analysis-grid" style={{marginTop:18}}><article className="panel full"><div className="eyebrow">Diagnosis</div><h2>{data.diagnosis}</h2><div className="stats-row"><span>Value: ₹{money(data.summary.current_value)}</span><span>Unrealized P&amp;L: ₹{money(data.summary.unrealized_pnl)}</span><span>Return on cost: {pct(data.summary.unrealized_pnl_pct)}</span><span>Daily P&amp;L: ₹{money(data.summary.daily_pnl)}</span></div></article>
      <article className="panel"><div className="eyebrow">Key Observations</div><div className="evidence-list">{data.key_observations.map((x,i)=><div key={i}>{x}</div>)}</div></article>
      <article className="panel"><div className="eyebrow">Risk Context</div><div className="evidence-list">{data.risk_observations.map((x,i)=><div key={i}>{x}</div>)}</div></article>
      <article className="panel full"><div className="eyebrow">Data Gaps</div><div className="evidence-list">{data.data_gaps.map((x,i)=><div key={i}>{x}</div>)}</div><div className="disclaimer">{data.method}</div></article>
    </section>}
  </AppShell>;
}
