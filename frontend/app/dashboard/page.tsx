"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { AppShell } from "../../components/AppShell";
import {
  API_BASE_URL,
  apiFetch,
  getAccessToken,
  refreshAccessToken,
} from "../../lib/api";

type IndexQuote = {
  exchange: "NSE" | "BSE";
  symbol: string | null;
  trade_date: string | null;
  close: number | null;
  previous_close: number | null;
  change_pct: number | null;
  data_status: string;
};

type EODMover = {
  symbol: string;
  name?: string | null;
  close?: number | null;
  change_pct?: number | null;
};

type EODExchange = {
  exchange: "NSE" | "BSE";
  data_status: string;
  trade_date: string | null;
  records: number;
  positive: number;
  negative: number;
  unchanged: number;
  breadth_pct: number | null;
  top_gainers: EODMover[];
  top_losers: EODMover[];
  source?: string;
  fetched_at?: string | null;
  ingestion_status?: string;
};

type Tick = {
  exchange: "NSE" | "BSE";
  symbol: string;
  name?: string | null;
  price?: number | null;
  change_pct?: number | null;
  as_of?: string;
};

type LiveProviderStatus = {
  provider_configured: boolean;
  provider_running: boolean;
  provider_connected: boolean;
  provider_type: string;
  status: string;
};

function formatPercent(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "--";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function EODCard({ item, exchange }: { item: EODExchange | undefined; exchange: "NSE" | "BSE" }) {
  const available = Boolean(item && item.records > 0 && item.trade_date);

  return (
    <article className="panel">
      <div className="section-title">
        <div>
          <div className="eyebrow">{exchange} · End of day</div>
          <h2>{available ? item.trade_date : "No EOD dataset"}</h2>
        </div>
        <span className="caption">{available ? "Stored EOD" : "Unavailable"}</span>
      </div>
      <div className="metric">{available ? item.records.toLocaleString() : "--"}</div>
      <div className="caption">Securities in latest session</div>
      <div className="stats-row">
        <span>Advancers: {available ? item.positive : "--"}</span>
        <span>Decliners: {available ? item.negative : "--"}</span>
        <span>Unchanged: {available ? item.unchanged : "--"}</span>
        <span>Breadth: {available ? formatPercent(item.breadth_pct) : "--"}</span>
      </div>
      {available && item.fetched_at && (
        <p className="caption">
          Ingested {new Date(item.fetched_at).toLocaleString()}
        </p>
      )}
      {available && item.source && (
        <p className="caption">Source: {item.source}</p>
      )}
      {!available && (
        <p className="muted">
          This exchange has no stored EOD session yet. No live price is substituted.
        </p>
      )}
    </article>
  );
}

export default function DashboardPage() {
  const [connection, setConnection] = useState("connecting");
  const [ticks, setTicks] = useState<Record<string, Tick>>({});
  const [indices, setIndices] = useState<IndexQuote[]>([]);
  const [eod, setEod] = useState<EODExchange[]>([]);
  const [eodError, setEodError] = useState("");
  const [providerStatus, setProviderStatus] = useState<LiveProviderStatus | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttempt = useRef(0);

  useEffect(() => {
    let active = true;

    apiFetch<{ exchanges: EODExchange[] }>("/api/v1/market/eod/overview")
      .then((data) => {
        if (active) {
          setEod(data.exchanges || []);
          setEodError("");
        }
      })
      .catch((error) => {
        if (active) {
          setEod([]);
          setEodError(error instanceof Error ? error.message : "Unable to load EOD data");
        }
      });

    apiFetch<{ indices: IndexQuote[] }>("/api/v1/market/index/overview")
      .then((data) => {
        if (active) setIndices(data.indices || []);
      })
      .catch(() => {
        if (active) setIndices([]);
      });

    apiFetch<LiveProviderStatus>("/api/v1/live/status")
      .then((data) => {
        if (active) setProviderStatus(data);
      })
      .catch(() => {
        if (active) setProviderStatus(null);
      });

    const connect = async () => {
      if (!active) return;

      let token = getAccessToken();
      if (!token) {
        const refreshed = await refreshAccessToken();
        if (!refreshed) {
          if (active) setConnection("unauthenticated");
          return;
        }
        token = getAccessToken();
      }
      if (!token || !active) return;

      setConnection(
        reconnectAttempt.current === 0 ? "connecting" : "reconnecting",
      );

      const wsBase =
        process.env.NEXT_PUBLIC_WS_BASE_URL ||
        API_BASE_URL.replace(/^http/, "ws");
      const socket = new WebSocket(
        wsBase + "/api/v1/live/ws",
        ["sharem-auth", token],
      );
      socketRef.current = socket;

      socket.onopen = () => {
        reconnectAttempt.current = 0;
        if (active) setConnection("connected");
      };

      socket.onclose = async (event) => {
        if (!active) return;
        socketRef.current = null;

        if (event.code === 4401) {
          const refreshed = await refreshAccessToken();
          if (!refreshed) {
            setConnection("unauthenticated");
            return;
          }
          reconnectAttempt.current = 0;
        }

        setConnection("disconnected");
        const delay = Math.min(
          1000 * 2 ** reconnectAttempt.current,
          15000,
        );
        reconnectAttempt.current += 1;
        reconnectTimer.current = setTimeout(connect, delay);
      };

      socket.onerror = () => {
        if (active) setConnection("unavailable");
      };

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === "market.tick" && message.data?.symbol) {
            const tick = message.data as Tick;
            setTicks((current) => ({
              ...current,
              [tick.exchange + ":" + tick.symbol]: tick,
            }));
          }
        } catch {
          // Ignore malformed websocket frames.
        }
      };
    };

    void connect();

    return () => {
      active = false;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, []);

  const nseIndex = indices.find((item) => item.exchange === "NSE");
  const bseIndex = indices.find((item) => item.exchange === "BSE");
  const nseEod = eod.find((item) => item.exchange === "NSE");
  const bseEod = eod.find((item) => item.exchange === "BSE");

  const movers = useMemo(
    () =>
      Object.values(ticks)
        .filter((tick) => typeof tick.change_pct === "number")
        .sort(
          (a, b) =>
            Math.abs(b.change_pct ?? 0) - Math.abs(a.change_pct ?? 0),
        )
        .slice(0, 8),
    [ticks],
  );

  const providerLabel = !providerStatus
    ? "Provider status unavailable"
    : providerStatus.provider_connected
      ? `${providerStatus.provider_type} feed connected`
      : providerStatus.provider_running
        ? "Provider worker active · reconnecting"
        : providerStatus.provider_configured
          ? "Provider configured · worker not running"
          : "Provider not configured";

  return (
    <AppShell>
      <section className="page-heading">
        <div>
          <div className="eyebrow">Dashboard · EOD intelligence first</div>
          <h1>Market intelligence</h1>
          <p className="lead">
            Completed NSE/BSE sessions drive market diagnosis and AI explanations.
            Live prices are a separate, secondary monitoring feed.
          </p>
        </div>
        <Link href="/ai/market" className="button primary">
          Generate EOD Intelligence
        </Link>
      </section>

      <section className="panel">
        <div className="section-title">
          <div>
            <div className="eyebrow">Primary data layer</div>
            <h2>Latest completed trading session</h2>
          </div>
          <Link href="/markets" className="top-action">
            Full market overview
          </Link>
        </div>
        {eodError && <div className="error">{eodError}</div>}
        <div className="metric-grid">
          <EODCard item={nseEod} exchange="NSE" />
          <EODCard item={bseEod} exchange="BSE" />
        </div>
        <div className="caption" style={{ marginTop: 12 }}>
          EOD figures are used for market breadth, regime classification,
          historical indicators and AI analysis. Missing sessions remain
          unavailable; live ticks are never used as an EOD replacement.
        </div>
        <div className="grid-2" style={{ marginTop: 18 }}>
          <article>
            <div className="eyebrow">NSE top gainers</div>
            {nseEod?.top_gainers?.length ? (
              <div className="evidence-list">
                {nseEod.top_gainers.slice(0, 5).map((item) => (
                  <div key={item.symbol}>
                    <strong>{item.symbol}</strong>
                    <span> · {formatPercent(item.change_pct)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted">No NSE EOD movers available.</p>
            )}
          </article>
          <article>
            <div className="eyebrow">NSE top losers</div>
            {nseEod?.top_losers?.length ? (
              <div className="evidence-list">
                {nseEod.top_losers.slice(0, 5).map((item) => (
                  <div key={item.symbol}>
                    <strong>{item.symbol}</strong>
                    <span> · {formatPercent(item.change_pct)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted">No NSE EOD movers available.</p>
            )}
          </article>
        </div>
      </section>

      <section className="metric-grid" style={{ marginTop: 18 }}>
        {[
          [
            "NSE Index EOD",
            nseIndex?.close == null ? "--" : nseIndex.close.toLocaleString(),
            nseIndex?.symbol
              ? nseIndex.symbol + " · " + (nseIndex.trade_date ?? "--")
              : "Index source not configured",
          ],
          [
            "BSE Index EOD",
            bseIndex?.close == null ? "--" : bseIndex.close.toLocaleString(),
            bseIndex?.symbol
              ? bseIndex.symbol + " · " + (bseIndex.trade_date ?? "--")
              : "Index source not configured",
          ],
          [
            "EOD sessions",
            String([nseEod, bseEod].filter((item) => item && item.records > 0).length),
            "Exchanges with stored EOD data",
          ],
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
          <div>
            <div className="eyebrow">Secondary data layer</div>
            <h2>Live market monitor</h2>
          </div>
          <span className="caption">App WebSocket: {connection}</span>
        </div>
        <p className="muted">
          {providerLabel}. The app socket can be connected even when an external
          broker feed has not been configured.
        </p>
        {movers.length === 0 ? (
          <div className="empty">
            No live ticks received. EOD analysis remains available independently.
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Exchange</th>
                  <th>Price</th>
                  <th>Change</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {movers.map((tick) => (
                  <tr key={tick.exchange + tick.symbol}>
                    <td>{tick.symbol}</td>
                    <td>{tick.exchange}</td>
                    <td>{tick.price ?? "--"}</td>
                    <td>{formatPercent(tick.change_pct)}</td>
                    <td>
                      {tick.as_of
                        ? new Date(tick.as_of).toLocaleTimeString()
                        : "--"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel" style={{ marginTop: 18 }}>
        <div className="eyebrow">Research workspace</div>
        <h2>Explain the completed market session</h2>
        <p className="muted">
          Generate NSE-first diagnosis with breadth, sectors, institutional
          activity, corporate events, regime detection, technical indicators
          and evidence-linked AI explanations.
        </p>
        <Link href="/ai/market" className="button primary">
          Open EOD intelligence
        </Link>
      </section>
    </AppShell>
  );
}
