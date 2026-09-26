import Link from "next/link";
import { AppShell } from "../../components/AppShell";
import { SectionPage } from "../../components/SectionPage";

export default function SettingsPage() {
  return <AppShell><SectionPage eyebrow="Settings" title="Account settings" description="Manage your profile, AI language preference, security and sessions." /><div className="grid-two"><section className="panel"><h2>AI language</h2><p className="muted">English, Tamil, Hindi, Gujarati and Kannada apply to AI explanations only.</p></section><section className="panel"><h2>Security</h2><p className="muted">Password, two-factor authentication and active sessions.</p><div className="actions"><Link className="button" href="/settings/security">Security</Link><Link className="button" href="/settings/sessions">Sessions</Link></div></section></div></AppShell>;
}
