"use client";

import { FormEvent, useState } from "react";
import { AppShell } from "../../../components/AppShell";
import { apiFetch } from "../../../lib/api";

type Analysis = {
  analysis_id: string;
  analysis_type: string;
  trade_date: string;
  status: string;
  market_metrics: {
    nse_stocks: number; positive: number; negative: number; unchanged: number;
    breadth_pct?: number | null; mean_change_pct?: number | null;
  };
  regime: { label: string; reasons: string[] };
  disclaimer: string;
};

export default function MarketAIPage() {
  const [symbol, setSymbol] = useState("");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function generate(event: FormEvent) {
    event.preventDefault();
    setLoading(true); setError(""); setAnalysis(null);
    try {
      const endpoint = symbol.trim()
        ? `/api/v1/intelligence/eod?symbol=${encodeURIComponent(symbol.trim())}`
        : "/api/v1/intelligence/eod";
      setAnalysis(await apiFetch<Analysis>(endpoint, { method: "POST" }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to generate analysis");
    } finally { setLoading(false); }
  }

  return (
    <AppShell>
      <section className="page-heading">
        <div><div className="eyebrow">AI Intelligence / Market</div><h1>EOD market intelligence</h1><p className="lead">Generate the market report first, then investigate a selected stock using the same validated EOD dataset.</p></div>
      </section>
      <section className="panel">
        <form onSubmit={generate} className="analysis-form">
          <label>Stock symbol <span className="muted">(optional)</span>
            <input value={symbol} onChange={(e)=>setSymbol(e.target.value.toUpperCase())} placeholder="e.g. RELIANCE" maxLength={32} />
          </label>
          <button className="button primary" disabled={loading}>{loading ? "Generating..." : "Generate EOD Intelligence"}</button>
        </form>
        {error && <div className="error">{error}</div>}
      </section>
      {analysis && <section className="analysis-grid">
        <article className="panel"><div className="eyebrow">AI Diagnosis</div><h2>{analysis.regime.label}</h2><p className="muted">Trade date: {analysis.trade_date}</p><div className="evidence-list">{analysis.regime.reasons.map((r)=> <div key={r}>{r}</div>)}</div></article>
        <article className="panel"><div className="eyebrow">Market Evidence</div><div className="metric">{analysis.market_metrics.nse_stocks}</div><div className="muted">NSE records analysed</div><div className="stats-row"><span>Positive: {analysis.market_metrics.positive}</span><span>Negative: {analysis.market_metrics.negative}</span><span>Unchanged: {analysis.market_metrics.unchanged}</span></div><div className="stats-row"><span>Breadth: {analysis.market_metrics.breadth_pct?.toFixed(2) ?? "--"}%</span><span>Mean move: {analysis.market_metrics.mean_change_pct?.toFixed(2) ?? "--"}%</span></div></article>
        <article className="panel full"><div className="eyebrow">Analysis Snapshot</div><p className="muted">Analysis ID: {analysis.analysis_id}</p><div className="disclaimer">{analysis.disclaimer}</div></article>
      </section>}
    </AppShell>
  );
}
