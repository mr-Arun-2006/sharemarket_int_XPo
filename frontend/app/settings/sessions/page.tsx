"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "../../../components/AppShell";
import { apiFetch } from "../../../lib/api";

type Session = {
  session_id: string;
  created_at: string;
  last_used_at: string;
  expires_at: string;
  revoked_at: string | null;
};

export default function SessionsPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [error, setError] = useState("");

  async function load() {
    try {
      const result = await apiFetch<{sessions:Session[]}>("/api/v1/sessions");
      setSessions(result.sessions);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load sessions");
    }
  }

  useEffect(() => { load(); }, []);

  async function revoke(sessionId: string) {
    try {
      await apiFetch(`/api/v1/sessions/${sessionId}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to revoke session");
    }
  }

  return (
    <AppShell>
      <section className="page-heading">
        <div>
          <div className="eyebrow">Security</div>
          <h1>Sessions</h1>
          <p className="lead">Review and revoke active sessions for your account.</p>
        </div>
        <Link className="button" href="/settings">Back to settings</Link>
      </section>
      <section className="panel">
        {error && <div className="error">{error}</div>}
        {sessions.filter((session) => !session.revoked_at).map((session) => (
          <div key={session.session_id} className="session-row">
            <div>
              <strong>Active session</strong>
              <div className="caption">Created {new Date(session.created_at).toLocaleString()}</div>
              <div className="caption">Last used {new Date(session.last_used_at).toLocaleString()}</div>
            </div>
            <button className="button" onClick={() => revoke(session.session_id)}>Revoke</button>
          </div>
        ))}
        {!sessions.some((session) => !session.revoked_at) && <div className="empty">No active sessions.</div>}
      </section>
    </AppShell>
  );
}
