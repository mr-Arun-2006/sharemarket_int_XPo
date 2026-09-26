import Link from "next/link";
import { AppShell } from "../../components/AppShell";
import { SectionPage } from "../../components/SectionPage";

export default function StrategiesPage() {
  return <AppShell><SectionPage eyebrow="Strategy & Backtesting" title="Research and test strategies" description="Build strategy rules, run backtests and inspect result history." actions={[{label:"Strategy Builder",href:"/strategies/builder",primary:true},{label:"Backtest",href:"/strategies/backtest"}]} /><div className="grid-two"><section className="panel"><h2>Strategy Builder</h2><p className="muted">Define technical entry/exit rules and test parameters.</p><Link className="button" href="/strategies/builder">Open</Link></section><section className="panel"><h2>Results</h2><p className="muted">Saved backtest runs and historical results.</p><Link className="button" href="/strategies/results">View results</Link></section></div></AppShell>;
}
