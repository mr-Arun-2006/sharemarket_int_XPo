import Link from "next/link";

export default function HomePage() {
  return (
    <main className="shell">
      <nav className="nav">
        <div className="brand">ShareM Int Xpo</div>
        <div className="navlinks">
          <Link href="/product">Product</Link><Link href="/features">Features</Link><Link href="/intelligence">Intelligence</Link><Link href="/about">About</Link>
        </div>
        <div className="actions"><Link className="button" href="/register">Register</Link><Link className="button" href="/login">Login</Link></div>
      </nav>
      <section className="hero">
        <div className="eyebrow">Share Market Intelligence</div>
        <h1>See the market. Understand what happened.</h1>
        <p className="lead">Live price monitoring during market hours. Deep, evidence-backed end-of-day intelligence after the session.</p>
        <div className="actions"><Link className="button primary" href="/dashboard">Open Dashboard</Link><Link className="button" href="/intelligence">Explore Intelligence</Link></div>
      </section>
      <section className="grid">
        <article className="card"><div className="eyebrow">Live Market</div><h2>Monitor</h2><p className="muted">WebSocket-based index and mover monitoring with clear freshness status.</p></article>
        <article className="card"><div className="eyebrow">EOD Intelligence</div><h2>Diagnose</h2><p className="muted">NSE-first market analysis, BSE comparison and five-session context.</p></article>
        <article className="card"><div className="eyebrow">AI Explanation</div><h2>Understand</h2><p className="muted">Detailed explanations linked directly to measured market evidence.</p></article>
      </section>
    </main>
  );
}
