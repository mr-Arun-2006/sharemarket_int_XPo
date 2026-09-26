import Link from "next/link";

const live = [
  ["NIFTY 50", "--", "Waiting for WebSocket"],
  ["SENSEX", "--", "Waiting for WebSocket"],
  ["Top movers", "--", "Waiting for live feed"],
];

export default function DashboardPage() {
  return (
    <main className="shell">
      <nav className="nav">
        <div className="brand">ShareM Int Xpo</div>
        <div className="actions">
          <Link className="button" href="/intelligence">AI Intelligence</Link>
          <Link className="button" href="/login">Logout</Link>
        </div>
      </nav>

      <section>
        <div className="eyebrow">Dashboard</div>
        <h1>Live market</h1>
        <p className="lead">Simple monitoring first. Deep EOD intelligence is the main analysis layer below.</p>
      </section>

      <section className="grid">
        {live.map(([title, value, status]) => (
          <article className="card" key={title}>
            <div className="muted">{title}</div>
            <div className="metric">{value}</div>
            <div className="muted">{status}</div>
          </article>
        ))}
      </section>

      <section className="card" style={{ marginTop: 16 }}>
        <div className="eyebrow">EOD Intelligence</div>
        <h2>Generate after the trading session</h2>
        <p className="muted">NSE-first market analysis, BSE comparison, sectors, breadth, institutional activity, major events and evidence-linked AI explanation.</p>
        <div className="actions"><Link className="button primary" href="/intelligence">Generate EOD Intelligence</Link></div>
      </section>
    </main>
  );
}
