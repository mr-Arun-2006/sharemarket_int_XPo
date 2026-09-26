import Link from "next/link";

export default function HomePage() {
  return (
    <main className="shell">
      <nav className="nav">
        <div className="brand">ShareM Int Xpo</div>
        <div className="navlinks">
          <Link href="/product">Product</Link>
          <Link href="/features">Features</Link>
          <Link href="/intelligence">Intelligence</Link>
          <Link href="/about">About</Link>
        </div>
        <Link className="button" href="/login">Login</Link>
      </nav>

      <section className="hero">
        <div className="eyebrow">Share Market Intelligence</div>
        <h1>See the market. Understand what happened.</h1>
        <p className="lead">
          Lightweight live-price monitoring during market hours, followed by deep,
          evidence-backed end-of-day intelligence after the session.
        </p>
        <div className="actions">
          <Link className="button primary" href="/dashboard">Open Dashboard</Link>
          <Link className="button" href="/intelligence">Explore Intelligence</Link>
        </div>
      </section>

      <section className="grid">
        <article className="card">
          <div className="eyebrow">Live Market</div>
          <h2>Monitor</h2>
          <p className="muted">WebSocket price stream, indices and relevant movers.</p>
        </article>
        <article className="card">
          <div className="eyebrow">EOD Intelligence</div>
          <h2>Diagnose</h2>
          <p className="muted">NSE-first market analysis with BSE comparison and evidence.</p>
        </article>
        <article className="card">
          <div className="eyebrow">AI Explanation</div>
          <h2>Understand</h2>
          <p className="muted">Detailed explanation tied to measured market evidence.</p>
        </article>
      </section>
    </main>
  );
}
