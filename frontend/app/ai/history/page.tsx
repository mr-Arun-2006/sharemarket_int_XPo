"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "../../../components/AppShell";
import { apiFetch } from "../../../lib/api";

type Row={analysis_id:string;analysis_type:string;trade_date:string;generated_at:string;language:string;status:string;ai_provider:string;hierarchy?:{market?:{diagnosis?:string};selected_stock?:{symbol?:string}}};
type Compare={original:{trade_date:string;market_metrics:Record<string,number|null>;stock:Record<string,number|null>|null};latest:{trade_date:string;market_metrics:Record<string,number|null>;stock:Record<string,number|null>|null};comparison:{market:{metric:string;original:number|null;latest:number|null}[];stock:{metric:string;original:number|null;latest:number|null}[]}};

const num=(v:number|null|undefined)=>v==null?"--":v.toFixed(2);

export default function AIHistoryPage(){
  const [q,setQ]=useState(""); const [type,setType]=useState(""); const [rows,setRows]=useState<Row[]>([]); const [compare,setCompare]=useState<Compare|null>(null); const [error,setError]=useState("");
  async function load(){setError("");const qs=new URLSearchParams({limit:"50"});if(q)qs.set("q",q);if(type)qs.set("analysis_type",type);try{setRows((await apiFetch<{analyses:Row[]}>("/api/v1/intelligence/history?"+qs.toString())).analyses);}catch(err){setError(err instanceof Error?err.message:"Unable to load history");}}
  async function compareLatest(id:string){setError("");try{setCompare(await apiFetch<Compare>("/api/v1/intelligence/"+encodeURIComponent(id)+"/compare-latest"));}catch(err){setError(err instanceof Error?err.message:"Unable to compare analysis");}}
  useEffect(()=>{load()},[]);
  return <AppShell><section className="page-heading"><div><div className="eyebrow">AI Intelligence / History</div><h1>Analysis history</h1><p className="lead">Saved EOD analyses remain preserved. Opening an item uses the latest dataset for a separate comparison.</p></div></section>
    <section className="panel"><div className="actions"><input value={q} onChange={e=>setQ(e.target.value)} placeholder="Search analysis ID or stock symbol" /><select value={type} onChange={e=>setType(e.target.value)}><option value="">All types</option><option value="market">Market</option><option value="stock">Stock</option></select><button className="button primary" onClick={load}>Search</button></div>{error&&<div className="error">{error}</div>}</section>
    <section className="panel" style={{marginTop:18}}><div className="table-wrap"><table><thead><tr><th>Trade Date</th><th>Type</th><th>Stock</th><th>Diagnosis</th><th>Language</th><th>Generated</th><th>Actions</th></tr></thead><tbody>{rows.map(row=><tr key={row.analysis_id}><td>{row.trade_date}</td><td>{row.analysis_type}</td><td>{row.hierarchy?.selected_stock?.symbol??"--"}</td><td>{row.hierarchy?.market?.diagnosis??"--"}</td><td>{row.language}</td><td>{new Date(row.generated_at).toLocaleString()}</td><td><Link className="button" href={"/ai/market?analysis="+encodeURIComponent(row.analysis_id)}>Open</Link>{" "}<button className="button" onClick={()=>compareLatest(row.analysis_id)}>Compare latest</button></td></tr>)}{rows.length===0&&<tr><td colSpan={7}>No saved analyses found.</td></tr>}</tbody></table></div></section>
    {compare&&<section className="analysis-grid"><article className="panel full"><div className="eyebrow">Historical Comparison</div><h2>{compare.original.trade_date} vs {compare.latest.trade_date}</h2><p className="muted">Original output is preserved; the table below contains only measured changes from the current EOD dataset.</p><div className="table-wrap"><table><thead><tr><th>Metric</th><th>Original</th><th>Latest</th></tr></thead><tbody>{compare.comparison.market.map(r=><tr key={r.metric}><td>{r.metric}</td><td>{r.original==null?"--":num(r.original)}</td><td>{r.latest==null?"--":num(r.latest)}</td></tr>)}{compare.comparison.stock.map(r=><tr key={"stock-"+r.metric}><td>{r.metric}</td><td>{r.original==null?"--":num(r.original)}</td><td>{r.latest==null?"--":num(r.latest)}</td></tr>)}</tbody></table></div></article></section>}
  </AppShell>;
}
