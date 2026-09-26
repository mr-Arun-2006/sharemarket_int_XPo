import Link from "next/link";
import { AppShell } from "../../../components/AppShell";

export default function MarketReportsPage() {
  return <AppShell><section className="page-heading"><div><div className="eyebrow">Reports / Market</div><h1>Market reports</h1><p className="lead">Create a professional PDF from a completed EOD market analysis.</p></div></section><section className="panel"><h2>Start from EOD Intelligence</h2><p className="muted">Generate the current market analysis, review its evidence and export the preserved result as PDF.</p><div className="actions"><Link className="button primary" href="/ai/market">Open AI Intelligence</Link><Link className="button" href="/reports/history">Report history</Link></div></section></AppShell>;
}
