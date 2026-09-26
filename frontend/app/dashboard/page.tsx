"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { AppShell } from "../../components/AppShell";
import { API_BASE_URL, apiFetch } from "../../lib/api";

type IndexQuote = {
  exchange: "NSE" | "BSE";
  symbol: string | null;
  trade_date: string | null;
  close: number | null;
  previous_close: number | null;
  change_pct: number | null;
  data_status: string;
};

type Tick = {
  exchange: "NSE" | "BSE";
  symbol: string;
  name?: string | null;
  price?: number | null;
  change_pct?: number | null;
  as_of?: string;
};

export default function DashboardPage() {
  const [connection, setConnection] = useState("connecting");
  const [ticks, setTicks] = useState<Record<string, Tick>>({});
  const [indices, setIndices] = useState<IndexQuote[]>([]);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttempt = useRef(0);

  useEffect(() => {
    let active = true;
    apiFetch<{indices: IndexQuote[]}>("/api/v1/market/index/overview")
      .then((data) => { if (active) setIndices(data.indices || []); })
      .catch(() => { if (active) setIndices([]); });

    const connect = () => {
      if (!active) return;
      setConnection(reconnectAttempt.current === 0 ? "connecting" : "reconnecting");
      const socket = new WebSocket((process.env.NEXT_PUBLIC_WS_BASE_URL || API_BASE_URL.replace(/^http/, "ws")) + "/api/v1/live/ws");
      socketRef.current = socket;
      socket.onopen = () => { reconnectAttempt.current = 0; if (active) setConnection("live"); };
      socket.onclose = () => {
        if (!active) return;
        setConnection("disconnected");
        const delay = Math.min(1000 * 2 ** reconnectAttempt.current, 15000);
        reconnectAttempt.current += 1;
        reconnectTimer.current = setTimeout(connect, delay);
      };
      socket.onerror = () => { if (active) setConnection("unavailable"); };
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === "market.tick" && message.data?.symbol) {
            const tick = message.data as Tick;
            setTicks((current) => ({ ...current, [tick.exchange + ":" + tick.symbol]: tick }));
          }
        } catch {
          // Ignore malformed websocket frames.
        }
      };
    };
    connect();
    return () => {
      active = false;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, []);

  const nseIndex = indices.find((item) => item.exchange === "NSE");
  const bseIndex = indices.find((item) => item.exchange === "BSE");

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
          ["NSE Index", nseIndex?.close == null ? "--" : nseIndex.close.toLocaleString(), nseIndex?.symbol ? nseIndex.symbol + " · " + (nseIndex.trade_date ?? "--") : "Index source unavailable"],
          ["BSE Index", bseIndex?.close == null ? "--" : bseIndex.close.toLocaleString(), bseIndex?.symbol ? bseIndex.symbol + " · " + (bseIndex.trade_date ?? "--") : "Index source unavailable"],
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
