import Link from "next/link";
import { AppShell } from "../../../components/AppShell";
import { SectionPage } from "../../../components/SectionPage";

export default function SecurityPage() {
  return <AppShell>
    <SectionPage eyebrow="Security" title="Account security" description="Password, two-factor authentication and session security." actions={[{label:"Sessions",href:"/settings/sessions",primary:true}]} />
    <section className="grid-two">
      <article className="panel"><h2>Password</h2><p className="muted">Password changes will require current-password verification.</p></article>
      <article className="panel"><h2>Two-factor authentication</h2><p className="muted">TOTP/OTP security controls will be connected in the next authentication hardening stage.</p></article>
    </section>
  </AppShell>;
}
