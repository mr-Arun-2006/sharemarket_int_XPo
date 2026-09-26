"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { apiFetch } from "../../lib/api";

type Analysis = {
  analysis_id: string;
  analysis_type: string;
  trade_date: string;
  status: string;
  market_metrics: {
    nse_stocks: number;
    positive: number;
    negative: number;
    unchanged: number;
    breadth_pct?: number | null;
    mean_change_pct?: number | null;
  };
  regime: { label: string; reasons: string[] };
  disclaimer: string;
};

export default function IntelligencePage() {
  const [symbol, setSymbol] = useState("");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function generate(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setAnalysis(null);

    try {
      const path = symbol.trim()
        ? `/api/v1/intelligence/eod?symbol=${encodeURIComponent(symbol.trim())}`
        : "/api/v1/intelligence/eod";
      const result = await apiFetch<Analysis>(path, { method: "POST" });
      setAnalysis(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to generate analysis");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <Link href="/" className="brand">ShareM Int Xpo</Link>
        <nav className="toplinks">
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/intelligence">AI Intelligence</Link>
        </nav>
      </header>

      <section className="page-heading">
        <div>
          <div className="eyebrow">AI Intelligence</div>
          <h1>EOD market intelligence</h1>
          <p className="lead">Generate the market report first, then investigate a selected stock.</p>
        </div>
      </section>

      <section className="panel">
        <form onSubmit={generate} className="analysis-form">
          <label>
            Stock symbol <span className="muted">(optional)</span>
            <input
              value={symbol}
              onChange={(event) => setSymbol(event.target.value.toUpperCase())}
              placeholder="e.g. RELIANCE"
              maxLength={32}
            />
          </label>
          <button className="button primary" disabled={loading}>
            {loading ? "Generating..." : "Generate EOD Intelligence"}
          </button>
        </form>
        {error && <div className="error">{error}</div>}
      </section>

      {analysis && (
        <section className="analysis-grid">
          <article className="panel">
            <div className="eyebrow">AI Diagnosis</div>
            <h2>{analysis.regime.label}</h2>
            <p className="muted">Trade date: {analysis.trade_date}</p>
            <div className="evidence-list">
              {analysis.regime.reasons.map((reason) => <div key={reason}>{reason}</div>)}
            </div>
          </article>

          <article className="panel">
            <div className="eyebrow">Market Evidence</div>
            <div className="metric">{analysis.market_metrics.nse_stocks}</div>
            <div className="muted">NSE records analysed</div>
            <div className="stats-row">
              <span>Positive: {analysis.market_metrics.positive}</span>
              <span>Negative: {analysis.market_metrics.negative}</span>
              <span>Unchanged: {analysis.market_metrics.unchanged}</span>
            </div>
            <div className="stats-row">
              <span>Breadth: {analysis.market_metrics.breadth_pct?.toFixed(2) ?? "--"}%</span>
              <span>Mean move: {analysis.market_metrics.mean_change_pct?.toFixed(2) ?? "--"}%</span>
            </div>
          </article>

          <article className="panel full">
            <div className="eyebrow">Analysis Snapshot</div>
            <p className="muted">
              Analysis {analysis.analysis_id} was generated for {analysis.analysis_type} intelligence.
              The current EOD engine returns measured market evidence; the AI explanation gateway is the next enrichment layer.
            </p>
            <div className="disclaimer">{analysis.disclaimer}</div>
          </article>
        </section>
      )}
    </main>
  );
}
