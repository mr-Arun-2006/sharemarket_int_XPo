import Link from "next/link";
import { AppShell } from "../../../components/AppShell";
import { SectionPage } from "../../../components/SectionPage";

export default function AIStockPage() { return <AppShell><SectionPage eyebrow="AI Intelligence / Stock" title="Deep stock analysis" description="EOD prices, five-session context, technicals, fundamentals and market context for a selected stock." actions={[{label:"Market Analysis",href:"/ai/market",primary:true}]} /><section className="panel"><input placeholder="Enter stock symbol" /><div className="actions"><Link href="/stocks" className="button primary">Select stock</Link></div></section></AppShell>; }
