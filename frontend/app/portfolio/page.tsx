import { AppShell } from "../../components/AppShell";
import { SectionPage } from "../../components/SectionPage";

export default function PortfolioPage() {
  return <AppShell><SectionPage eyebrow="Portfolio" title="Portfolio intelligence" description="Holdings, P&L, allocation, exposure, risk metrics, benchmarks and portfolio AI intelligence." /><div className="metric-grid"><article className="panel"><div className="muted">Portfolio Value</div><div className="metric">--</div></article><article className="panel"><div className="muted">Unrealized P&L</div><div className="metric">--</div></article><article className="panel"><div className="muted">Risk</div><div className="metric">--</div></article></div></AppShell>;
}
