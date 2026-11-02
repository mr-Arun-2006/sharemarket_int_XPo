"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  checkFirebaseEmailVerified,
  exchangeFirebaseSession,
  getFirebaseSessionEmail,
  sendFirebaseVerificationEmail,
} from "../../lib/firebase-auth";

export default function VerifyPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);

  useEffect(() => {
    setEmail(getFirebaseSessionEmail());
  }, []);

  async function completeVerification() {
    setLoading(true);
    setMessage("");
    try {
      const verified = await checkFirebaseEmailVerified();
      if (!verified) {
        setMessage("Firebase has not marked this email as verified yet. Open the latest verification email, then try again.");
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
        return;
      }
      throw new Error("The backend did not create an application session.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to complete verification");
    } finally {
      setLoading(false);
    }
  }

  async function resendVerification() {
    setResending(true);
    setMessage("");
    try {
      await sendFirebaseVerificationEmail();
      setMessage("A new Firebase verification email has been sent.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to resend verification email");
    } finally {
      setResending(false);
    }
  }

  return (
    <main className="shell">
      <nav className="nav">
        <div className="brand">ShareM Int Xpo</div>
        <Link className="button" href="/login">Sign in</Link>
      </nav>
      <section className="card" style={{ maxWidth: 520, margin: "40px auto" }}>
        <div className="eyebrow">Firebase email verification</div>
        <h2>Verify your email</h2>
        <p className="muted">
          {email ? "A verification link was sent to " + email + "." : "Open the verification link sent to your email address."}
          {" "}After clicking the link, return here and confirm verification.
        </p>
        <div className="actions">
          <button className="button primary" disabled={loading} onClick={completeVerification}>
            {loading ? "Checking..." : "I have verified my email"}
          </button>
          <button className="button" disabled={resending || !email} onClick={resendVerification}>
            {resending ? "Sending..." : "Resend email"}
          </button>
        </div>
        {message && <p className="muted" style={{ marginTop: 16 }}>{message}</p>}
      </section>
    </main>
  );
}
