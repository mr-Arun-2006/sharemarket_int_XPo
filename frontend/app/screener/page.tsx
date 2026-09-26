import Link from "next/link";
import { AppShell } from "../../components/AppShell";
import { SectionPage } from "../../components/SectionPage";

export default function ScreenerPage() {
  return <AppShell><SectionPage eyebrow="Screener" title="Find market conditions" description="Build, save and run stock screens using technical, fundamental and market-activity filters." actions={[{label:"Builder",href:"/screener/builder",primary:true},{label:"AI Screener",href:"/screener/ai"}]} /><div className="grid-two"><section className="panel"><h2>Quick Screen</h2><p className="muted">Create a rule set to filter the current stock universe.</p><Link className="button primary" href="/screener/builder">Open builder</Link></section><section className="panel"><h2>Saved Screens</h2><p className="muted">Your saved screen definitions and recent results.</p><Link className="button" href="/screener/saved">View saved</Link></section></div></AppShell>;
}
