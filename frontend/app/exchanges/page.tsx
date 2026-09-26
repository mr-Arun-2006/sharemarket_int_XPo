"use client";

import { useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { apiFetch } from "../../lib/api";

type Mover={symbol:string;change_pct:number|null;close:number|null};
type Exchange={exchange:"NSE"|"BSE";data_status:string;trade_date:string|null;records:number;positive:number;negative:number;unchanged:number;breadth_pct:number|null;average_change_pct:number|null;total_volume:number|null;total_turnover:number|null;top_gainers:Mover[];top_losers:Mover[];source?:string|null;fetched_at?:string|null};
type Pair={symbol:string;nse_change_pct:number;bse_change_pct:number;spread_pct:number};
type Comparison={generated_at:string;exchanges:{NSE:Exchange;BSE:Exchange};index_performance:unknown[];index_note:string;stock_level_comparison:{matched_symbols:number;largest_change_spreads:Pair[]}};

const fmt=(v:number|null|undefined,d=2)=>v==null?"--":v.toLocaleString(undefined,{maximumFractionDigits:d});
const signed=(v:number|null|undefined)=>v==null?"--":(v>=0?"+":"")+v.toFixed(2)+"%";

export default function ExchangesPage(){
  const [data,setData]=useState<Comparison|null>(null); const [error,setError]=useState("");
  useEffect(()=>{apiFetch<Comparison>("/api/v1/exchanges/comparison").then(setData).catch(e=>setError(e instanceof Error?e.message:"Unable to load exchange comparison"));},[]);

  const nse=data?.exchanges.NSE, bse=data?.exchanges.BSE;
  const rows=[
    ["Trade date",nse?.trade_date,bse?.trade_date],
    ["Securities",fmt(nse?.records,0),fmt(bse?.records,0)],
    ["Advancing",fmt(nse?.positive,0),fmt(bse?.positive,0)],
    ["Declining",fmt(nse?.negative,0),fmt(bse?.negative,0)],
    ["Unchanged",fmt(nse?.unchanged,0),fmt(bse?.unchanged,0)],
    ["Breadth",signed(nse?.breadth_pct),signed(bse?.breadth_pct)],
    ["Average change",signed(nse?.average_change_pct),signed(bse?.average_change_pct)],
    ["Total volume",fmt(nse?.total_volume,0),fmt(bse?.total_volume,0)],
    ["Total turnover",fmt(nse?.total_turnover,0),fmt(bse?.total_turnover,0)],
  ];

  return <AppShell>
    <section className="page-heading"><div><div className="eyebrow">NSE vs BSE</div><h1>Exchange comparison</h1><p className="lead">Unified EOD comparison using normalized equity-market records. Values are shown only when corresponding data is available.</p></div></section>
    {error&&<div className="error">{error}</div>}

    <section className="metric-grid">
      {(["NSE","BSE"] as const).map(ex=><article className="panel" key={ex}><div className="eyebrow">{ex}</div><div className="metric">{data?.exchanges[ex].trade_date??"--"}</div><div className="caption">{data?.exchanges[ex].data_status??"Loading"} · {fmt(data?.exchanges[ex].records,0)} securities · {data?.exchanges[ex].fetched_at?"updated "+new Date(data.exchanges[ex].fetched_at as string).toLocaleString():"--"}</div></article>)}
      <article className="panel"><div className="eyebrow">Matched symbols</div><div className="metric">{fmt(data?.stock_level_comparison.matched_symbols,0)}</div><div className="caption">Exact symbol matches available on both exchanges</div></article>
    </section>

    <section className="panel" style={{marginTop:18}}><div className="section-title"><div><div className="eyebrow">Market Snapshot</div><h2>Side-by-side metrics</h2></div><span className="caption">{data?.generated_at ? new Date(data.generated_at).toLocaleString() : "Loading"}</span></div>
      <div className="table-wrap"><table><thead><tr><th>Metric</th><th>NSE</th><th>BSE</th></tr></thead><tbody>{rows.map(r=><tr key={r[0]}><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td></tr>)}</tbody></table></div>
    </section>

    <section className="analysis-grid">
      <section className="panel"><div className="eyebrow">Performance Charts</div><h2>Breadth</h2><div className="stats-row"><span>NSE {signed(nse?.breadth_pct)}</span><span>BSE {signed(bse?.breadth_pct)}</span></div>
        <div style={{marginTop:18}}>{(["NSE","BSE"] as const).map(ex=>{const value=Math.max(-100,Math.min(100,data?.exchanges[ex].breadth_pct??0));return <div key={ex} style={{marginBottom:16}}><div className="section-title"><span>{ex}</span><span className="caption">{signed(data?.exchanges[ex].breadth_pct)}</span></div><div style={{height:10,borderRadius:999,background:"var(--surface-2)",overflow:"hidden"}}><div style={{width:Math.abs(value)+"%",height:"100%",marginLeft:value<0? (100-Math.abs(value))+"%":"0",background:"var(--primary)",opacity:.8}}/></div></div>})}</div>
      </section>
      <section className="panel"><div className="eyebrow">Index Performance</div><h2>Index series status</h2><p className="muted">{data?.index_note??"Loading index-source status..."}</p><div className="empty">No index values are inferred from equity EOD rows.</div></section>
    </section>

    <section className="panel" style={{marginTop:18}}><div className="eyebrow">Stock-Level Comparison</div><h2>Largest NSE/BSE daily-change spreads</h2>
      {!data?<div className="empty">Loading comparison...</div>:data.stock_level_comparison.largest_change_spreads.length===0?<div className="empty">No exact symbol matches are available for both exchanges.</div>:
      <div className="table-wrap"><table><thead><tr><th>Symbol</th><th>NSE Change</th><th>BSE Change</th><th>Spread</th></tr></thead><tbody>{data.stock_level_comparison.largest_change_spreads.map(r=><tr key={r.symbol}><td>{r.symbol}</td><td>{signed(r.nse_change_pct)}</td><td>{signed(r.bse_change_pct)}</td><td>{signed(r.spread_pct)}</td></tr>)}</tbody></table></div>}
    </section>

    <section className="panel" style={{marginTop:18}}><div className="eyebrow">Top Movers</div><div className="grid-2">
      {(["NSE","BSE"] as const).map(ex=><div key={ex}><h3>{ex}</h3><div className="table-wrap"><table><thead><tr><th>Symbol</th><th>Change</th><th>Close</th></tr></thead><tbody>{(data?.exchanges[ex].top_gainers??[]).slice(0,5).map((r:any)=><tr key={r.symbol}><td>{r.symbol}</td><td>{signed(r.change_pct)}</td><td>{fmt(r.close)}</td></tr>)}</tbody></table></div></div>)}
    </div></section>
  </AppShell>
}
