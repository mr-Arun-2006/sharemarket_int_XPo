"use client";

import { FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AppShell } from "../../../components/AppShell";
import { apiDownload, apiFetch } from "../../../lib/api";

type Section={status:string;diagnosis?:string|null;summary?:string;key_reasons?:string[];symbol?:string;latest?:{trade_date:string;close:number|null;change_pct:number|null};technical?:Record<string,number|null|undefined>;evidence?:unknown[];leaders?:{sector:string;stocks_covered:number;average_change_pct:number;positive:number;negative:number}[];rows?:{category:string;buy_value:number|null;sell_value:number|null;net_value:number|null}[];items?:{symbol?:string|null;subject:string;details:string;broadcast_at?:string;source_url?:string}[]};
type Analysis={
  analysis_id:string; analysis_type:string; trade_date:string; status:string; language:string;
  market_metrics:{nse_stocks:number;positive:number;negative:number;unchanged:number;breadth_pct:number|null;mean_change_pct:number|null};
  regime:{label:string;reasons:string[]};
  hierarchy:Record<string,Section>;
  evidence:{id:string;type:string;label:string;value:unknown;source:string}[];
  uncertainty:string[];
  ai_provider:string; ai_narrative:string|null; disclaimer:string;
};

const languages=[["en","English"],["ta","Tamil"],["hi","Hindi"],["gu","Gujarati"],["kn","Kannada"]];

export default function MarketAIPage(){
  const searchParams=useSearchParams();
  const historicalId=searchParams.get("analysis");
  const [symbol,setSymbol]=useState(""); const [language,setLanguage]=useState("en");
  const [analysis,setAnalysis]=useState<Analysis|null>(null); const [error,setError]=useState(""); const [loading,setLoading]=useState(false);
  async function generate(event:FormEvent){
    event.preventDefault();setLoading(true);setError("");setAnalysis(null);
    try{
      const query=new URLSearchParams({language});
      if(symbol.trim()) query.set("symbol",symbol.trim());
      setAnalysis(await apiFetch<Analysis>("/api/v1/intelligence/eod?"+query.toString(),{method:"POST"}));
    }catch(err){setError(err instanceof Error?err.message:"Unable to generate analysis");}
    finally{setLoading(false);}
  }
  const status=(s?:Section)=>s?.status==="missing"?"Missing source data":"Available";
  async function exportPdf() {
    if (!analysis) return;
    setError("");
    try {
      const created = await apiFetch<{report_id:string}>("/api/v1/reports/from-analysis/" + encodeURIComponent(analysis.analysis_id), { method: "POST" });
      const blob = await apiDownload("/api/v1/reports/" + encodeURIComponent(created.report_id) + "/pdf");
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = created.report_id + ".pdf";
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "PDF export failed");
    }
  }


  useEffect(()=>{
    if(!historicalId) return;
    apiFetch<Analysis>("/api/v1/intelligence/"+encodeURIComponent(historicalId))
      .then(setAnalysis)
      .catch(err=>setError(err instanceof Error?err.message:"Unable to load historical analysis"));
  },[historicalId]);

  return <AppShell>
    <section className="page-heading"><div><div className="eyebrow">AI Intelligence / Market</div><h1>EOD market intelligence</h1><p className="lead">Generate a source-grounded diagnosis from the validated EOD dataset. Deep stock analysis uses the same evidence layer.</p></div></section>
    <section className="panel"><form onSubmit={generate} className="analysis-form">
      <label>Stock symbol <span className="muted">(optional)</span><input value={symbol} onChange={e=>setSymbol(e.target.value.toUpperCase())} placeholder="e.g. RELIANCE" maxLength={32}/></label>
      <label>AI explanation language<select value={language} onChange={e=>setLanguage(e.target.value)}>{languages.map(([code,label])=><option value={code} key={code}>{label}</option>)}</select></label>
      <button className="button primary" disabled={loading}>{loading?"Generating...":"Generate EOD Intelligence"}</button>
    </form>{error&&<div className="error">{error}</div>}</section>

    {analysis&&<section className="analysis-grid">
      <article className="panel full"><div className="section-title"><div><div className="eyebrow">Overall Diagnosis</div></div><button className="button primary" onClick={exportPdf}>Export PDF</button></div><h2>{analysis.hierarchy.market?.diagnosis??analysis.regime.label}</h2><p className="muted">{analysis.hierarchy.market?.summary}</p><div className="evidence-list">{(analysis.hierarchy.market?.key_reasons??analysis.regime.reasons).map((x,i)=><div key={i}>{x}</div>)}</div></article>

      <article className="panel"><div className="eyebrow">Market Evidence</div><div className="metric">{analysis.market_metrics.nse_stocks}</div><div className="muted">NSE records analysed</div><div className="stats-row"><span>Positive: {analysis.market_metrics.positive}</span><span>Negative: {analysis.market_metrics.negative}</span><span>Unchanged: {analysis.market_metrics.unchanged}</span><span>Breadth: {analysis.market_metrics.breadth_pct==null?"--":analysis.market_metrics.breadth_pct.toFixed(2)+"%"}</span></div></article>

      <article className="panel"><div className="eyebrow">Selected Stock</div><h2>{analysis.hierarchy.selected_stock?.symbol??"Not selected"}</h2><p className="muted">{analysis.hierarchy.selected_stock?.diagnosis??"Run with a symbol to include deep stock context."}</p>{analysis.hierarchy.selected_stock?.latest&&<div className="stats-row"><span>Close: {analysis.hierarchy.selected_stock.latest.close??"--"}</span><span>Change: {analysis.hierarchy.selected_stock.latest.change_pct==null?"--":analysis.hierarchy.selected_stock.latest.change_pct.toFixed(2)+"%"}</span></div>}</article>

      {[
        ["Sectors","sectors"],["Institutional Activity","institutional_activity"],["Major Events","major_events"]
      ].map(([title,key])=>{const section=analysis.hierarchy[key];return <article className="panel" key={key}><div className="eyebrow">{title}</div><h2>{section?.diagnosis??status(section)}</h2><p className="muted">{section?.summary}</p>
        {key==="sectors"&&section?.leaders&&section.leaders.length>0&&<div className="table-wrap"><table><thead><tr><th>Sector</th><th>Stocks</th><th>Avg Change</th></tr></thead><tbody>{section.leaders.slice(0,6).map(x=><tr key={x.sector}><td>{x.sector}</td><td>{x.stocks_covered}</td><td>{x.average_change_pct.toFixed(2)}%</td></tr>)}</tbody></table></div>}
        {key==="institutional_activity"&&section?.rows&&section.rows.length>0&&<div className="table-wrap"><table><thead><tr><th>Category</th><th>Buy</th><th>Sell</th><th>Net</th></tr></thead><tbody>{section.rows.map(x=><tr key={x.category}><td>{x.category}</td><td>{x.buy_value??"--"}</td><td>{x.sell_value??"--"}</td><td>{x.net_value??"--"}</td></tr>)}</tbody></table></div>}
        {key==="major_events"&&section?.items&&section.items.length>0&&<div className="evidence-list">{section.items.slice(0,5).map((x,i)=><div key={i}><strong>{x.symbol??"--"}</strong> · {x.subject}<br/><span className="caption">{x.broadcast_at??"--"}</span></div>)}</div>}
      </article>})}

      <article className="panel full"><div className="eyebrow">AI Narrative</div><h2>{analysis.ai_provider==="generated"?"Provider-generated explanation":"Evidence-grounded baseline explanation"}</h2>{analysis.ai_narrative?<p style={{whiteSpace:"pre-wrap",lineHeight:1.7}}>{analysis.ai_narrative}</p>:<p className="muted">No external AI provider is configured. The system returned the deterministic evidence-grounded diagnosis and explicitly marked unavailable data.</p>}</article>

      <article className="panel full"><div className="eyebrow">Evidence & Sources</div><div className="table-wrap"><table><thead><tr><th>ID</th><th>Type</th><th>Evidence</th><th>Source</th></tr></thead><tbody>{analysis.evidence.map(item=><tr key={item.id}><td>{item.id}</td><td>{item.type}</td><td>{item.label}</td><td>{item.source}</td></tr>)}</tbody></table></div></article>

      <article className="panel full"><div className="eyebrow">Uncertainty</div><div className="evidence-list">{analysis.uncertainty.map((x,i)=><div key={i}>{x}</div>)}</div><div className="disclaimer">{analysis.disclaimer}</div></article>
    </section>}
  </AppShell>;
}
