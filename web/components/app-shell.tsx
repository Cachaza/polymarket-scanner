import Link from "next/link";
import type { Route } from "next";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Overview" },
  { href: "/markets", label: "Markets" },
  { href: "/watchlist", label: "Watchlist" },
  { href: "/alerts", label: "Alerts" },
  { href: "/recommendations", label: "Recommendations" },
  { href: "/research", label: "Research" },
  { href: "/guide", label: "Guide" },
  { href: "/system", label: "System" },
] satisfies Array<{ href: Route; label: string }>;

export function AppShell({
  children,
  currentPath,
}: {
  children: ReactNode;
  currentPath: string;
}) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(70,132,183,0.12),_transparent_32%),linear-gradient(180deg,_#f8fbff_0%,_#eef4fb_100%)] text-ink">
      <div className="mx-auto flex max-w-7xl flex-col gap-8 px-4 py-6 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-5 rounded-[28px] border border-white/70 bg-white/80 px-5 py-5 shadow-panel backdrop-blur sm:px-6">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-accent">Polymarket Scanner Console</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">Signal review for scanner scope</h1>
            </div>
            <p className="max-w-2xl text-sm leading-6 text-slate-600">
              Internal console for scanner health, watchlist triage, alert review, and strategy feedback loops.
            </p>
          </div>
          <nav className="flex flex-wrap gap-2">
            {navItems.map((item) => {
              const active = currentPath === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "rounded-full border px-4 py-2 text-sm font-medium transition",
                    active
                      ? "border-accent bg-accent text-white"
                      : "border-line bg-white text-slate-600 hover:border-accent hover:text-accent",
                  )}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </header>
        {children}
      </div>
    </div>
  );
}
