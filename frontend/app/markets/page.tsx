import { AppShell } from "../../components/AppShell";
import { SectionPage } from "../../components/SectionPage";

export default function MarketsPage() {
  return <AppShell><SectionPage eyebrow="Markets" title="Market overview" description="Indices, sectors, breadth, institutional activity and sentiment across the Indian market." /><div className="metric-grid"><article className="panel"><div className="eyebrow">NIFTY 50</div><div className="metric">--</div><div className="caption">Live / EOD status will appear here.</div></article><article className="panel"><div className="eyebrow">SENSEX</div><div className="metric">--</div><div className="caption">Live / EOD status will appear here.</div></article><article className="panel"><div className="eyebrow">Market Breadth</div><div className="metric">--</div><div className="caption">Advance / decline data.</div></article></div></AppShell>;
}
