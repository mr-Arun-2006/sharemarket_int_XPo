import Link from "next/link";
import { AppShell } from "../../components/AppShell";
import { SectionPage } from "../../components/SectionPage";

export default function ReportsPage() {
  return <AppShell><SectionPage eyebrow="Reports" title="Research reports" description="Market, stock, portfolio and backtest reports generated from validated data and AI analysis." /><div className="grid-two"><section className="panel"><h2>Market Reports</h2><p className="muted">EOD market intelligence reports and history.</p><Link className="button" href="/reports/market">Open</Link></section><section className="panel"><h2>Report History</h2><p className="muted">Previously generated reports.</p><Link className="button" href="/reports/history">Open</Link></section></div></AppShell>;
}
