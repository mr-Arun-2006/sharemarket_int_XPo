import Link from "next/link";

export function SectionPage({
  eyebrow,
  title,
  description,
  actions = [],
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  actions?: { label: string; href: string; primary?: boolean }[];
  children?: React.ReactNode;
}) {
  return (
    <>
      <section className="page-heading">
        <div>
          <div className="eyebrow">{eyebrow}</div>
          <h1>{title}</h1>
          <p className="lead">{description}</p>
        </div>
        <div className="actions">
          {actions.map((action) => (
            <Link key={action.href} href={action.href} className={action.primary ? "button primary" : "button"}>
              {action.label}
            </Link>
          ))}
        </div>
      </section>
      {children}
    </>
  );
}
