import Link from "next/link";
import { AppShell } from "../../components/AppShell";
import { SectionPage } from "../../components/SectionPage";

export default function AIPage() {
  return <AppShell><SectionPage eyebrow="AI Intelligence" title="Market intelligence workspace" description="Generate deep EOD explanations from validated market evidence, or investigate an individual stock." actions={[{label:"Market Analysis",href:"/ai/market",primary:true},{label:"AI Chat",href:"/ai/chat"}]} /><div className="grid-two"><section className="panel"><h2>EOD Market Analysis</h2><p className="muted">NSE-first analysis with BSE comparison and five-session historical context.</p><Link className="button primary" href="/ai/market">Open</Link></section><section className="panel"><h2>History</h2><p className="muted">Every completed analysis is automatically preserved for later comparison.</p><Link className="button" href="/ai/history">Open history</Link></section></div></AppShell>;
}
