import { AppShell } from "../../components/AppShell";
import { SectionPage } from "../../components/SectionPage";

export default function WatchlistPage() {
  return <AppShell><SectionPage eyebrow="Watchlist" title="Your watchlists" description="Monitor selected stocks with live prices, EOD changes and AI-driven market events." /><section className="panel"><h2>Default Watchlist</h2><div className="table-wrap"><table><thead><tr><th>Symbol</th><th>Price</th><th>Change</th><th>Volume</th><th>Status</th></tr></thead><tbody><tr><td>--</td><td>--</td><td>--</td><td>--</td><td>Waiting</td></tr></tbody></table></div></section></AppShell>;
}
