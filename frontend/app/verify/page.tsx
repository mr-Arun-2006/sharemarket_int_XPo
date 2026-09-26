"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { apiFetch } from "../../lib/api";

export default function VerifyPage() {
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [message, setMessage] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await apiFetch("/api/v1/auth/verify", { method:"POST", body:JSON.stringify({email, otp}) });
      setMessage("Email verified. You can now sign in.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Verification failed");
    }
  }

  return (
    <main className="shell">
      <nav className="nav"><div className="brand">ShareM Int Xpo</div><Link className="button" href="/login">Login</Link></nav>
      <section className="card" style={{maxWidth:520, margin:"40px auto"}}>
        <div className="eyebrow">Verification</div>
        <h2>Verify email</h2>
        <form onSubmit={submit}>
          <input value={email} onChange={(e)=>setEmail(e.target.value)} type="email" placeholder="Email" required style={{width:"100%",padding:12,margin:"8px 0 16px",background:"var(--surface-2)",color:"var(--text)",border:"1px solid var(--border)",borderRadius:10}} />
          <input value={otp} onChange={(e)=>setOtp(e.target.value)} inputMode="numeric" pattern="\d{6}" maxLength={6} placeholder="6-digit OTP" required style={{width:"100%",padding:12,margin:"8px 0 16px",background:"var(--surface-2)",color:"var(--text)",border:"1px solid var(--border)",borderRadius:10}} />
          <button className="button primary">Verify email</button>
        </form>
        {message && <p className="muted" style={{marginTop:16}}>{message}</p>}
      </section>
    </main>
  );
}
