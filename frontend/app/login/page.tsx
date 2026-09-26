"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiFetch, setAccessToken } from "../../lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    try {
      const result = await apiFetch<{
        status: string;
        access_token?: string;
        challenge_id?: string;
        requires_2fa?: boolean;
      }>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });

      if (result.requires_2fa && result.challenge_id) {
        sessionStorage.setItem("sharem_2fa_challenge", result.challenge_id);
        router.push("/2fa");
        return;
      }

      if (result.access_token) {
        setAccessToken(result.access_token);
        router.push("/dashboard");
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="shell">
      <nav className="nav">
        <div className="brand">ShareM Int Xpo</div>
        <Link className="button" href="/">Back</Link>
      </nav>
      <section className="card" style={{ maxWidth: 520, margin: "40px auto" }}>
        <div className="eyebrow">Authentication</div>
        <h2>Sign in</h2>
        <p className="muted">Access your market workspace.</p>
        <form onSubmit={submit}>
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            type="email"
            placeholder="Email"
            autoComplete="email"
            required
          />
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            minLength={8}
            placeholder="Password"
            autoComplete="current-password"
            required
          />
          <div className="actions">
            <button className="button primary" disabled={loading}>
              {loading ? "Signing in..." : "Sign in"}
            </button>
            <Link className="button" href="/register">Create account</Link>
          </div>
        </form>
        {message && <p className="error">{message}</p>}
      </section>
    </main>
  );
}
