"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { exchangeFirebaseSession, signInWithFirebase } from "../../lib/firebase-auth";

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
      const emailVerified = await signInWithFirebase(email, password);
      if (!emailVerified) {
        setMessage("Your email is not verified yet. Complete the verification step.");
        router.push("/verify");
        return;
      }

      const result = await exchangeFirebaseSession();
      if (result.requires_2fa && result.challenge_id) {
        sessionStorage.setItem("sharem_2fa_challenge", result.challenge_id);
        router.push("/2fa");
        return;
      }
      if (result.access_token) {
        router.push("/dashboard");
      } else {
        throw new Error("The backend did not create an application session.");
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
        <div className="eyebrow">Firebase Authentication</div>
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
            minLength={6}
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
