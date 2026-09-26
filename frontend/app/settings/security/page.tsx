"use client";

import { useState } from "react";
import { AppShell } from "../../../components/AppShell";
import { apiFetch } from "../../../lib/api";

export default function SecurityPage() {
  const [secret, setSecret] = useState("");
  const [code, setCode] = useState("");
  const [status, setStatus] = useState("");

  async function setup() {
    try {
      const result = await apiFetch<{secret:string;otpauth_url:string}>("/api/v1/auth/2fa/setup", {method:"POST"});
      setSecret(result.secret);
      setStatus("Setup created. Add the secret to your authenticator, then verify it below.");
    } catch (error) { setStatus(error instanceof Error ? error.message : "Unable to start 2FA setup"); }
  }

  async function enable() {
    try {
      await apiFetch("/api/v1/auth/2fa/enable", {method:"POST",body:JSON.stringify({code})});
      setSecret(""); setCode(""); setStatus("Two-factor authentication enabled.");
    } catch (error) { setStatus(error instanceof Error ? error.message : "Unable to enable 2FA"); }
  }

  return <AppShell><section className="page-heading"><div><div className="eyebrow">Security</div><h1>Account security</h1><p className="lead">Password, two-factor authentication and session security.</p></div></section><section className="panel"><h2>Two-factor authentication</h2><p className="muted">Use a TOTP authenticator. The application stores the TOTP secret server-side after verification.</p><div className="actions"><button className="button primary" onClick={setup}>Set up 2FA</button></div>{secret && <><p className="caption">Secret (keep private):</p><code>{secret}</code><input value={code} onChange={(e)=>setCode(e.target.value)} inputMode="numeric" pattern="\d{6}" maxLength={6} placeholder="Authenticator code" style={{marginTop:14}}/><div className="actions"><button className="button primary" onClick={enable}>Enable 2FA</button></div></>}{status && <p className="muted" style={{marginTop:14}}>{status}</p>}</section></AppShell>;
}
