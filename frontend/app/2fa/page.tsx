"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, setAccessToken } from "../../lib/api";

export default function TwoFactorLoginPage() {
  const router = useRouter();
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const challenge_id = sessionStorage.getItem("sharem_2fa_challenge");
    if (!challenge_id) {
      setMessage("Two-factor challenge has expired. Please sign in again.");
      return;
    }

    setLoading(true);
    setMessage("");
    try {
      const result = await apiFetch<{ access_token: string }>(
        "/api/v1/auth/2fa/verify-login",
        {
          method: "POST",
          body: JSON.stringify({ challenge_id, code }),
        },
      );
      setAccessToken(result.access_token);
      sessionStorage.removeItem("sharem_2fa_challenge");
      router.push("/dashboard");
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Two-factor verification failed",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="shell">
      <section className="card" style={{ maxWidth: 460, margin: "80px auto" }}>
        <div className="eyebrow">Security</div>
        <h1>Two-factor verification</h1>
        <p className="lead">Enter the six-digit code from your authenticator app.</p>
        <form onSubmit={submit}>
          <input
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
            inputMode="numeric"
            pattern="\d{6}"
            maxLength={6}
            autoComplete="one-time-code"
            required
            placeholder="000000"
          />
          <div className="actions">
            <button className="button primary" disabled={loading}>
              {loading ? "Verifying..." : "Verify"}
            </button>
          </div>
        </form>
        {message && <p className="error">{message}</p>}
      </section>
    </main>
  );
}
