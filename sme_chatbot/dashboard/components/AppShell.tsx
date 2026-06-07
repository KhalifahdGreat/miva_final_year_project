"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { Icon, type IconName } from "./icons";
import { TenantSwitcher } from "./TenantSwitcher";
import { AuthControls } from "@/lib/clerk";

type NavItem = { href: string; label: string; icon: IconName };

const NAV: { group: string; items: NavItem[] }[] = [
  {
    group: "Operate",
    items: [
      { href: "/dashboard", label: "Overview", icon: "grid" },
      { href: "/dashboard/conversations", label: "Conversations", icon: "chat" },
      { href: "/dashboard/analytics", label: "Analytics", icon: "chart" },
    ],
  },
  {
    group: "Configure",
    items: [
      { href: "/dashboard/knowledge", label: "Knowledge", icon: "book" },
      { href: "/dashboard/persona", label: "Persona & tone", icon: "persona" },
      { href: "/dashboard/channels", label: "Channels", icon: "plug" },
    ],
  },
  {
    group: "Test",
    items: [{ href: "/dashboard/playground", label: "Playground", icon: "play" }],
  },
];

const TITLES: Record<string, string> = {
  "/dashboard": "Overview",
  "/dashboard/conversations": "Conversations",
  "/dashboard/analytics": "Analytics",
  "/dashboard/knowledge": "Knowledge",
  "/dashboard/persona": "Persona & tone",
  "/dashboard/channels": "Channels",
  "/dashboard/playground": "Playground",
};

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() || "/dashboard";

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="logo">S</div>
          <div>
            <div className="name">SME Chatbot</div>
            <div className="sub">Customer-service AI</div>
          </div>
        </div>

        <nav style={{ overflowY: "auto" }}>
          {NAV.map((g) => (
            <div key={g.group}>
              <div className="nav-group-label">{g.group}</div>
              {g.items.map((it) => {
                const active = it.href === "/dashboard" ? pathname === it.href : pathname.startsWith(it.href);
                return (
                  <Link key={it.href} href={it.href} className={`nav-link ${active ? "active" : ""}`}>
                    <span className="nav-ico"><Icon name={it.icon} size={18} /></span>
                    {it.label}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="spacer" />
        <div className="side-foot">
          <div>v1.0 · Pilot</div>
          <div style={{ marginTop: 2 }}>Multilingual · EN · Pidgin · YO · HA · IG</div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <TenantSwitcher />
          <div className="grow" />
          <span className="badge badge-green dot">Live</span>
          <Link href="/dashboard/playground" className="btn btn-ghost btn-sm">
            <Icon name="play" size={14} /> Test bot
          </Link>
          <AuthControls />
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
