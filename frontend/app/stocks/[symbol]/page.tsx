"use client";

import { useEffect, useState } from "react";
import { AppShell } from "../../../components/AppShell";
import { apiFetch } from "../../../lib/api";

type StockResponse = {
  symbol:string; exchange:string; name?:string|null;
  latest:{trade_date:string;close:number|null;previous_close:number|null;change_pct:number|null;volume:number|null;data_status:string};
  technical:Record<string,number|null|undefined>; fundamentals?:Record<string,unknown>|null; fundamentals_status?:string;
  history:{trade_date:string;close:number|null;volume:number|null;change_pct:number|null}[];
};

export default function StockPage({ params }: { params: Promise<{symbol:string}> }) {
  const [symbol,setSymbol]=useState("");
  const [data,setData]=useState<StockResponse|null>(null);
  const [error,setError]=useState("");

  useEffect(()=>{
    params.then(p=>{
      const s=decodeURIComponent(p.symbol).toUpperCase();
      setSymbol(s);
      return apiFetch<StockResponse>("/api/v1/stocks/"+encodeURIComponent(s)+"?exchange=NSE&sessions=60");
    }).then(setData).catch(err=>setError(err instanceof Error ? err.message : "Unable to load stock"));
  },[params]);

  return <AppShell>
    <section className="page-heading"><div><div className="eyebrow">Stock Intelligence</div><h1>{symbol||"Stock"}</h1><p className="lead">{data?.name??"Loading latest EOD context, technical indicators and history."}</p></div></section>
    {error && <div className="error">{error}</div>}
    {data && <>
      <section className="metric-grid">
        <article className="panel"><div className="eyebrow">Latest Close</div><div className="metric">{data.latest.close??"--"}</div><div className="caption">{data.latest.trade_date} · {data.latest.change_pct==null?"--":data.latest.change_pct.toFixed(2)+"%"} · {data.latest.data_status}</div></article>
        <article className="panel"><div className="eyebrow">RSI 14</div><div className="metric">{data.technical.rsi_14==null?"--":Number(data.technical.rsi_14).toFixed(2)}</div><div className="caption">Technical snapshot</div></article>
        <article className="panel"><div className="eyebrow">SMA 20</div><div className="metric">{data.technical.sma_20==null?"--":Number(data.technical.sma_20).toFixed(2)}</div><div className="caption">20-session simple moving average</div></article>
        <article className="panel"><div className="eyebrow">Volatility</div><div className="metric">{data.technical.annualized_volatility_pct==null?"--":Number(data.technical.annualized_volatility_pct).toFixed(2)+"%"}</div><div className="caption">Annualized from available EOD history</div></article>
      </section>
      <section className="panel" style={{marginTop:18}}>
        <div className="section-title"><div><div className="eyebrow">Historical Performance</div><h2>Recent sessions</h2></div><span className="caption">NSE · EOD</span></div>
        <div className="table-wrap"><table><thead><tr><th>Date</th><th>Close</th><th>Change</th><th>Volume</th></tr></thead><tbody>
          {data.history.slice(-20).map(row=><tr key={row.trade_date}><td>{row.trade_date}</td><td>{row.close??"--"}</td><td>{row.change_pct==null?"--":row.change_pct.toFixed(2)+"%"}</td><td>{row.volume??"--"}</td></tr>)}
        </tbody></table></div>
      </section>
      <section className="panel" style={{marginTop:18}}>
        <div className="eyebrow">Fundamental Analysis</div><h2>{data.fundamentals_status==="available"?"Source-backed snapshot":"Fundamental data unavailable"}</h2>
        {data.fundamentals ? <div className="table-wrap"><table><tbody>
          {[
            ["Market Cap","market_cap"],["Enterprise Value","enterprise_value"],["Revenue","revenue"],["Net Income","net_income"],["EPS","eps"],["P/E","pe"],["P/B","pb"],["ROE %","roe_pct"],["ROCE %","roce_pct"],["Debt / Equity","debt_to_equity"],["Dividend Yield %","dividend_yield_pct"]
          ].map(([label,key])=><tr key={key}><th>{label}</th><td>{data.fundamentals?.[key] == null ? "--" : String(data.fundamentals[key])}</td></tr>)}
          <tr><th>As of</th><td>{String(data.fundamentals.as_of ?? "--")}</td></tr>
          <tr><th>Source</th><td>{String(data.fundamentals.source ?? "--")}</td></tr>
        </tbody></table></div> : <p className="muted">No fundamental snapshot is currently stored for this symbol. The system does not infer fundamentals from price data.</p>}
      </section>
      <section className="panel" style={{marginTop:18}}>
        <div className="eyebrow">Technical Analysis</div><h2>Indicator snapshot</h2>
        <div className="table-wrap"><table><tbody>
          <tr><th>EMA 20</th><td>{data.technical.ema_20==null?"--":Number(data.technical.ema_20).toFixed(2)}</td></tr>
          <tr><th>MACD</th><td>{data.technical.macd==null?"--":Number(data.technical.macd).toFixed(4)}</td></tr>
          <tr><th>MACD Histogram</th><td>{data.technical.macd_histogram==null?"--":Number(data.technical.macd_histogram).toFixed(4)}</td></tr>
          <tr><th>ATR 14</th><td>{data.technical.atr_14==null?"--":Number(data.technical.atr_14).toFixed(2)}</td></tr>
          <tr><th>Volume Ratio (5)</th><td>{data.technical.volume_ratio_5==null?"--":Number(data.technical.volume_ratio_5).toFixed(2)+"x"}</td></tr>
          <tr><th>Max Drawdown</th><td>{data.technical.max_drawdown_pct==null?"--":Number(data.technical.max_drawdown_pct).toFixed(2)+"%"}</td></tr>
        </tbody></table></div>
      </section>
    </>}
  </AppShell>;
}
