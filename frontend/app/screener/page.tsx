"use client";

import { useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { apiFetch } from "../../lib/api";

type Row={symbol:string;name?:string|null;close?:number|null;change_pct:number;volume?:number|null};
export default function ScreenerPage(){
  const [min,setMin]=useState(""); const [max,setMax]=useState(""); const [rows,setRows]=useState<Row[]>([]);
  const [loading,setLoading]=useState(true); const [error,setError]=useState("");
  async function run(){
    setLoading(true); setError("");
    const qs=new URLSearchParams({exchange:"NSE",sort_by:"change_pct",limit:"100"});
    if(min) qs.set("min_change_pct",min); if(max) qs.set("max_change_pct",max);
    try{const r=await apiFetch<{results:Row[]}>("/api/v1/screener/run?"+qs.toString());setRows(r.results);}
    catch(err){setError(err instanceof Error?err.message:"Unable to run screener");} finally{setLoading(false);}
  }
  useEffect(()=>{run()},[]);
  return <AppShell><section className="page-heading"><div><div className="eyebrow">Screener</div><h1>Find market conditions</h1><p className="lead">Filter the latest NSE EOD universe using transparent, data-backed conditions.</p></div></section>
    <section className="panel"><div className="actions"><input value={min} onChange={e=>setMin(e.target.value)} type="number" step="0.1" placeholder="Min change %" /><input value={max} onChange={e=>setMax(e.target.value)} type="number" step="0.1" placeholder="Max change %" /><button className="button primary" onClick={run}>Run screen</button></div></section>
    {error&&<div className="error" style={{marginTop:18}}>{error}</div>}
    <section className="panel" style={{marginTop:18}}><div className="section-title"><div><div className="eyebrow">Results</div><h2>Latest EOD matches</h2></div><span className="caption">{loading?"Loading...":rows.length+" rows"}</span></div>
    {loading?<div className="empty">Running screener...</div>:<div className="table-wrap"><table><thead><tr><th>Symbol</th><th>Name</th><th>Close</th><th>Change</th><th>Volume</th></tr></thead><tbody>{rows.map(r=><tr key={r.symbol}><td>{r.symbol}</td><td>{r.name??"--"}</td><td>{r.close??"--"}</td><td>{r.change_pct.toFixed(2)}%</td><td>{r.volume??"--"}</td></tr>)}</tbody></table></div>}</section>
  </AppShell>
}
