import Link from "next/link";

export default function LoginPage() {
  return (
    <main className="shell">
      <nav className="nav"><div className="brand">ShareM Int Xpo</div><Link className="button" href="/">Back</Link></nav>
      <section className="hero">
        <div className="eyebrow">Authentication</div>
        <h1>Sign in</h1>
        <p className="lead">Authentication API is connected to MongoDB Atlas. The frontend form will be wired next.</p>
        <div className="actions">
          <Link className="button primary" href="/dashboard">Continue to dashboard</Link>
        </div>
      </section>
    </main>
  );
}
