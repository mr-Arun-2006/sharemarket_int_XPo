import { AppShell } from "../../components/AppShell";
import { SectionPage } from "../../components/SectionPage";

export default function ExchangesPage() {
  return <AppShell><SectionPage eyebrow="NSE vs BSE" title="Exchange comparison" description="Unified analytical view comparing NSE primary data with BSE market context." /><section className="panel"><div className="table-wrap"><table><thead><tr><th>Metric</th><th>NSE</th><th>BSE</th><th>Comparison</th></tr></thead><tbody><tr><td>Index performance</td><td>--</td><td>--</td><td>--</td></tr><tr><td>Market breadth</td><td>--</td><td>--</td><td>--</td></tr><tr><td>Turnover</td><td>--</td><td>--</td><td>--</td></tr></tbody></table></div></section></AppShell>;
}
