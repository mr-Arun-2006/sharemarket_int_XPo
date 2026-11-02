"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createFirebaseAccount } from "../../lib/firebase-auth";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    if (password !== confirmPassword) {
      setMessage("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      await createFirebaseAccount(email, password);
      router.push("/verify");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Registration failed");
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
        <h2>Create account</h2>
        <p className="muted">Create your ShareM Int Xpo account. Firebase will send an email verification link.</p>
        <form onSubmit={submit}>
          <label className="muted">Email</label>
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            type="email"
            autoComplete="email"
            required
            style={{ width: "100%", padding: 12, margin: "8px 0 16px", background: "var(--surface-2)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 10 }}
          />
          <label className="muted">Password</label>
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            autoComplete="new-password"
            minLength={8}
            required
            style={{ width: "100%", padding: 12, margin: "8px 0 16px", background: "var(--surface-2)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 10 }}
          />
          <label className="muted">Confirm password</label>
          <input
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            type="password"
            autoComplete="new-password"
            minLength={8}
            required
            style={{ width: "100%", padding: 12, margin: "8px 0 16px", background: "var(--surface-2)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 10 }}
          />
          <button className="button primary" disabled={loading}>
            {loading ? "Creating account..." : "Create account"}
          </button>
        </form>
        {message && <p className="error" style={{ marginTop: 16 }}>{message}</p>}
      </section>
    </main>
  );
}
