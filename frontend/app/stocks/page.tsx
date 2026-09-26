"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { apiFetch } from "../../lib/api";

type Stock = { symbol:string; name?:string|null; close?:number|null; change_pct?:number|null };

export default function StocksPage() {
  const [q,setQ]=useState("");
  const [stocks,setStocks]=useState<Stock[]>([]);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");

  async function load(term="") {
    setLoading(true); setError("");
    try {
      const result=await apiFetch<{stocks:Stock[]}>("/api/v1/stocks?exchange=NSE&q="+encodeURIComponent(term)+"&limit=50");
      setStocks(result.stocks);
    } catch(err) {
      setError(err instanceof Error ? err.message : "Unable to load stocks");
    } finally { setLoading(false); }
  }

  useEffect(()=>{ load(); },[]);

  return <AppShell>
    <section className="page-heading"><div><div className="eyebrow">Stocks</div><h1>Stock intelligence</h1><p className="lead">Search the latest normalized NSE universe and open a stock analysis workspace.</p></div></section>
    <section className="panel">
      <div className="actions">
        <input value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>{if(e.key==="Enter") load(q)}} placeholder="Search symbol or company name" />
        <button className="button primary" onClick={()=>load(q)}>Search</button>
      </div>
    </section>
    {error && <div className="error" style={{marginTop:18}}>{error}</div>}
    <section className="panel" style={{marginTop:18}}>
      <div className="section-title"><div><div className="eyebrow">Latest EOD</div><h2>Stock universe</h2></div><span className="caption">{loading ? "Loading..." : stocks.length+" results"}</span></div>
      {loading ? <div className="empty">Loading market data...</div> :
        <div className="table-wrap"><table><thead><tr><th>Symbol</th><th>Name</th><th>Close</th><th>Change</th><th></th></tr></thead><tbody>
          {stocks.map(row=><tr key={row.symbol}><td>{row.symbol}</td><td>{row.name??"--"}</td><td>{row.close??"--"}</td><td>{row.change_pct==null?"--":row.change_pct.toFixed(2)+"%"}</td><td><Link className="button" href={"/stocks/"+encodeURIComponent(row.symbol)}>Open</Link></td></tr>)}
        </tbody></table></div>}
    </section>
  </AppShell>;
}
