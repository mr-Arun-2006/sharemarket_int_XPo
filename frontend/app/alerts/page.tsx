import { AppShell } from "../../components/AppShell";
import { SectionPage } from "../../components/SectionPage";

export default function AlertsPage() {
  return <AppShell><SectionPage eyebrow="Alerts" title="Alerts center" description="Price, technical, volume, AI event, sentiment and regime notifications." actions={[{label:"Create Alert",href:"#create",primary:true}]} /><section className="panel"><h2>Active alerts</h2><div className="empty">No alerts configured yet.</div></section></AppShell>;
}
