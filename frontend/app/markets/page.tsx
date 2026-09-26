"use client";

import { useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { apiFetch } from "../../lib/api";

type Mover = { symbol:string; name?:string|null; close?:number|null; change_pct?:number|null };
type ExchangeOverview = {
  exchange:"NSE"|"BSE"; data_status:string; trade_date:string|null; records:number;
  positive:number; negative:number; unchanged:number; breadth_pct:number|null;
  top_gainers:Mover[]; top_losers:Mover[]; source?:string; fetched_at?:string|null;
};

export default function MarketsPage() {
  const [data,setData]=useState<ExchangeOverview[]>([]);
  const [error,setError]=useState("");
  useEffect(() => {
    apiFetch<{exchanges:ExchangeOverview[]}>("/api/v1/market/eod/overview")
      .then(set => setData(set.exchanges))
      .catch(err => setError(err instanceof Error ? err.message : "Unable to load market data"));
  }, []);

  const nse=data.find(x=>x.exchange==="NSE");
  const bse=data.find(x=>x.exchange==="BSE");

  return <AppShell>
    <section className="page-heading"><div><div className="eyebrow">Markets</div><h1>Market overview</h1>
      <p className="lead">Exchange-normalized EOD data for NSE and BSE. Live monitoring remains a separate WebSocket layer.</p></div></section>
    {error && <div className="error">{error}</div>}
    <section className="metric-grid">
      {([["NSE",nse],["BSE",bse]] as const).map(([label,item]) =>
        <article className="panel" key={label}><div className="eyebrow">{label} EOD</div>
          <div className="metric">{item?.trade_date ?? "--"}</div>
          <div className="caption">{item?.records ?? 0} securities · {item?.data_status ?? "missing"} · breadth {item?.breadth_pct == null ? "--" : item.breadth_pct.toFixed(2) + "%"}</div>
        </article>
      )}
      <article className="panel"><div className="eyebrow">Market Breadth</div><div className="metric">{nse ? nse.positive + " / " + nse.negative : "--"}</div><div className="caption">NSE advancing / declining securities</div></article>
    </section>
    {nse && nse.records > 0 && <section className="panel" style={{marginTop:18}}>
      <div className="section-title"><div><div className="eyebrow">NSE</div><h2>Top movers</h2></div><span className="caption">{nse.trade_date}</span></div>
      <div className="grid-2"><div><h3>Top gainers</h3><div className="table-wrap"><table><thead><tr><th>Symbol</th><th>Close</th><th>Change</th></tr></thead><tbody>
        {nse.top_gainers.map(row => <tr key={row.symbol}><td>{row.symbol}</td><td>{row.close ?? "--"}</td><td>{row.change_pct?.toFixed(2)}%</td></tr>)}
      </tbody></table></div></div><div><h3>Top losers</h3><div className="table-wrap"><table><thead><tr><th>Symbol</th><th>Close</th><th>Change</th></tr></thead><tbody>
        {nse.top_losers.map(row => <tr key={row.symbol}><td>{row.symbol}</td><td>{row.close ?? "--"}</td><td>{row.change_pct?.toFixed(2)}%</td></tr>)}
      </tbody></table></div></div></div>
    </section>}
    <section className="panel" style={{marginTop:18}}><div className="eyebrow">Data Status</div><h2>Source freshness</h2><p className="muted">
      {nse?.fetched_at ? "NSE ingestion: " + new Date(nse.fetched_at).toLocaleString() : "NSE data not ingested yet."}
      {" · "}{bse?.fetched_at ? "BSE ingestion: " + new Date(bse.fetched_at).toLocaleString() : "BSE data not ingested yet."}
    </p></section>
  </AppShell>;
}
