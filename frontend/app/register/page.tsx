"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { apiFetch } from "../../lib/api";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    try {
      const result = await apiFetch<{ user_id: string; development_otp?: string }>("/api/v1/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      const otp = result.development_otp ? ` Development OTP: ${result.development_otp}` : "";
      setMessage("Registration created. Check your verification channel." + otp);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="shell">
      <nav className="nav"><div className="brand">ShareM Int Xpo</div><Link className="button" href="/">Back</Link></nav>
      <section className="card" style={{maxWidth:520, margin:"40px auto"}}>
        <div className="eyebrow">Authentication</div>
        <h2>Create account</h2>
        <p className="muted">Create your ShareM Int Xpo account.</p>
        <form onSubmit={submit}>
          <label className="muted">Email</label>
          <input value={email} onChange={(e)=>setEmail(e.target.value)} type="email" required style={{width:"100%",padding:12,margin:"8px 0 16px",background:"var(--surface-2)",color:"var(--text)",border:"1px solid var(--border)",borderRadius:10}} />
          <label className="muted">Password</label>
          <input value={password} onChange={(e)=>setPassword(e.target.value)} type="password" minLength={8} required style={{width:"100%",padding:12,margin:"8px 0 16px",background:"var(--surface-2)",color:"var(--text)",border:"1px solid var(--border)",borderRadius:10}} />
          <button className="button primary" disabled={loading}>{loading ? "Creating..." : "Create account"}</button>
        </form>
        {message && <p className="muted" style={{marginTop:16}}>{message}</p>}
      </section>
    </main>
  );
}
