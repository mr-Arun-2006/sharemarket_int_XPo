import { AppShell } from "../../../components/AppShell";
import { SectionPage } from "../../../components/SectionPage";

export default async function StockPage({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  return <AppShell><SectionPage eyebrow="Stock Intelligence" title={symbol.toUpperCase()} description="Overview, technicals, fundamentals, institutional activity, news, AI diagnosis and historical context." actions={[{label:"AI Diagnosis",href:"/ai/stock",primary:true}]} /><div className="grid-two"><section className="panel"><h2>Overview</h2><p className="muted">Live price and EOD context will be connected to the market data layer.</p></section><section className="panel"><h2>Technical Analysis</h2><p className="muted">RSI, MACD, moving averages, volatility and trend structure.</p></section></div></AppShell>;
}
