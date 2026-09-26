import { AppShell } from "../../components/AppShell";
import { SectionPage } from "../../components/SectionPage";

export default function AdminPage() {
  return <AppShell><SectionPage eyebrow="Admin" title="Platform administration" description="Centralized control for users, roles, data pipelines, AI configuration, cache, security, reports and audit logs." /><section className="grid-two"><article className="panel"><h2>System Health</h2><p className="muted">Database, ingestion, Redis and API health will appear here.</p></article><article className="panel"><h2>Audit & Errors</h2><p className="muted">Administrative audit events and platform errors.</p></article></section></AppShell>;
}
