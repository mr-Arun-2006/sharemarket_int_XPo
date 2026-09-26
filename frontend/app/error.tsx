"use client";

import { useEffect } from "react";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error("Unhandled application error", error);
  }, [error]);

  return (
    <main className="shell">
      <section className="card" style={{ maxWidth: 640, margin: "80px auto" }}>
        <div className="eyebrow">Application error</div>
        <h2>Something went wrong</h2>
        <p className="muted">The page could not be rendered. Retry the request or return to the dashboard.</p>
        <div className="actions">
          <button className="button primary" onClick={() => reset()}>Try again</button>
        </div>
      </section>
    </main>
  );
}
