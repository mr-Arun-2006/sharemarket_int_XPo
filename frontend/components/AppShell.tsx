"use client";

import Link from "next/link";
import { useState } from "react";

const primaryNav = [
  ["Dashboard", "/dashboard"],
  ["Markets", "/markets"],
  ["NSE vs BSE", "/exchanges"],
  ["Screener", "/screener"],
  ["Stocks", "/stocks"],
  ["Watchlist", "/watchlist"],
  ["Portfolio", "/portfolio"],
  ["Strategy & Backtesting", "/strategies"],
  ["AI Intelligence", "/ai"],
  ["Alerts", "/alerts"],
  ["Reports", "/reports"],
  ["Settings", "/settings"],
  ["Admin", "/admin"],
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="product-shell">
      <aside className={open ? "sidebar open" : "sidebar"}>
        <div className="sidebar-brand">
          <span className="brand-mark">SM</span>
          <div>
            <div className="brand">ShareM Int Xpo</div>
            <div className="caption">Market Intelligence</div>
          </div>
        </div>
        <nav className="sidebar-nav" aria-label="Primary navigation">
          {primaryNav.map(([label, href]) => (
            <Link key={href} href={href} onClick={() => setOpen(false)}>{label}</Link>
          ))}
        </nav>
      </aside>

      {open && <button className="sidebar-backdrop" aria-label="Close menu" onClick={() => setOpen(false)} />}

      <div className="product-main">
        <header className="product-topbar">
          <button className="menu-button" onClick={() => setOpen(true)} aria-label="Open menu">☰</button>
          <div className="global-search">AI Global Search</div>
          <div className="market-status"><span className="status-dot" /> Market Status</div>
          <Link className="top-action" href="/exchanges">NSE vs BSE</Link>
          <select className="language-select" defaultValue="English" aria-label="AI response language">
            <option>文 English</option>
            <option>文 தமிழ்</option>
            <option>文 हिंदी</option>
            <option>文 ગુજરાતી</option>
            <option>文 ಕನ್ನಡ</option>
          </select>
          <Link className="top-action" href="/alerts">Notifications</Link>
          <Link className="top-action" href="/settings">Profile</Link>
        </header>
        <div className="product-content">{children}</div>
      </div>
    </div>
  );
}
