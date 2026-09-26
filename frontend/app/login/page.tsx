"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { apiFetch } from "../../lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      const result = await apiFetch<{access_token:string}>("/api/v1/auth/login", {
        method:"POST",
        body: JSON.stringify({email, password}),
      });
      sessionStorage.setItem("sharem_access_token", result.access_token);
      window.location.href = "/dashboard";
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Login failed");
    }
  }

  return (
    <main className="shell">
      <nav className="nav"><div className="brand">ShareM Int Xpo</div><Link className="button" href="/">Back</Link></nav>
      <section className="card" style={{maxWidth:520, margin:"40px auto"}}>
        <div className="eyebrow">Authentication</div>
        <h2>Sign in</h2>
        <p className="muted">Access your market workspace.</p>
        <form onSubmit={submit}>
          <input value={email} onChange={(e)=>setEmail(e.target.value)} type="email" placeholder="Email" required style={{width:"100%",padding:12,margin:"8px 0 16px",background:"var(--surface-2)",color:"var(--text)",border:"1px solid var(--border)",borderRadius:10}} />
          <input value={password} onChange={(e)=>setPassword(e.target.value)} type="password" minLength={8} placeholder="Password" required style={{width:"100%",padding:12,margin:"8px 0 16px",background:"var(--surface-2)",color:"var(--text)",border:"1px solid var(--border)",borderRadius:10}} />
          <div className="actions">
            <button className="button primary">Sign in</button>
            <Link className="button" href="/register">Create account</Link>
          </div>
        </form>
        {message && <p className="muted" style={{marginTop:16}}>{message}</p>}
      </section>
    </main>
  );
}
