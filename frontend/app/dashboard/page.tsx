"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { AppShell } from "../../components/AppShell";

type Tick = {
  exchange: "NSE" | "BSE";
  symbol: string;
  name?: string | null;
  price?: number | null;
  change_pct?: number | null;
  as_of?: string;
};

const WS_URL = process.env.NEXT_PUBLIC_WS_BASE_URL || "ws://localhost:8000";

export default function DashboardPage() {
  const [connection, setConnection] = useState("connecting");
  const [ticks, setTicks] = useState<Record<string, Tick>>({});
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const socket = new WebSocket(WS_URL + "/api/v1/live/ws");
    socketRef.current = socket;
    socket.onopen = () => setConnection("live");
    socket.onclose = () => setConnection("disconnected");
    socket.onerror = () => setConnection("unavailable");
    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === "market.tick" && message.data?.symbol) {
          const tick = message.data as Tick;
          setTicks((current) => ({ ...current, [tick.symbol]: tick }));
        }
      } catch {
        // Ignore malformed websocket frames.
      }
    };
    return () => socket.close();
  }, []);

  const movers = useMemo(
    () => Object.values(ticks)
      .filter((tick) => typeof tick.change_pct === "number")
      .sort((a, b) => Math.abs(b.change_pct ?? 0) - Math.abs(a.change_pct ?? 0))
      .slice(0, 8),
    [ticks],
  );

  return (
    <AppShell>
      <section className="page-heading">
        <div>
          <div className="eyebrow">Dashboard</div>
          <h1>Market monitor</h1>
          <p className="lead">Live prices first. Deep EOD intelligence is the main analysis layer.</p>
        </div>
        <Link href="/ai/market" className="button primary">Generate EOD Intelligence</Link>
      </section>

      <section className="metric-grid">
        {[
          ["NIFTY 50", "--", connection === "live" ? "Live WebSocket" : "Live feed unavailable"],
          ["SENSEX", "--", connection === "live" ? "Live WebSocket" : "Live feed unavailable"],
          ["Live movers", String(movers.length), "Adaptive market ranking"],
        ].map(([title, value, status]) => (
          <article className="panel" key={title}>
            <div className="muted">{title}</div>
            <div className="metric">{value}</div>
            <div className="caption">{status}</div>
          </article>
        ))}
      </section>

      <section className="panel" style={{ marginTop: 18 }}>
        <div className="section-title">
          <div><div className="eyebrow">Live Market</div><h2>Relevant movers</h2></div>
          <span className="caption">No polling fallback</span>
        </div>
        {movers.length === 0 ? (
          <div className="empty">Waiting for live market ticks.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Symbol</th><th>Exchange</th><th>Price</th><th>Change</th><th>Updated</th></tr></thead>
              <tbody>
                {movers.map((tick) => (
                  <tr key={tick.exchange + tick.symbol}>
                    <td>{tick.symbol}</td><td>{tick.exchange}</td><td>{tick.price ?? "--"}</td>
                    <td>{tick.change_pct?.toFixed(2)}%</td>
                    <td>{tick.as_of ? new Date(tick.as_of).toLocaleTimeString() : "--"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel" style={{ marginTop: 18 }}>
        <div className="eyebrow">EOD Intelligence</div>
        <h2>Understand what happened after the session</h2>
        <p className="muted">NSE-first analysis with BSE comparison, sectors, breadth, institutional activity, major events, regime detection and evidence-linked explanation.</p>
        <Link href="/ai/market" className="button primary">Open EOD workspace</Link>
      </section>
    </AppShell>
  );
}
