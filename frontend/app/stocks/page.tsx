import Link from "next/link";
import { AppShell } from "../../components/AppShell";
import { SectionPage } from "../../components/SectionPage";

export default function StocksPage() {
  return <AppShell><SectionPage eyebrow="Stocks" title="Stock intelligence" description="Search a symbol and open a complete analysis workspace." /><section className="panel"><h2>Search stock</h2><input placeholder="Search symbol or company name" /><div className="actions"><Link className="button primary" href="/stocks/RELIANCE">Open example workspace</Link></div></section></AppShell>;
}
