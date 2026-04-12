import type { Route } from "next";
import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { SectionHeader } from "@/components/section-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const workflow = [
  {
    title: "Start on Overview",
    body: "Check snapshot freshness, watchlist count, and recent job runs first. If the database is stale, everything downstream is lower confidence.",
    href: "/",
  },
  {
    title: "Filter markets before drilling in",
    body: "Use Markets to narrow by open or closed status, history readiness, watchlist membership, and sort order. Ending soon, holder-heavy, and watchlist-first sorts are the fastest ways to triage.",
    href: "/markets",
  },
  {
    title: "Use Watchlist for active review",
    body: "The watchlist is the compact queue of candidates the scoring logic thinks deserve attention. Warm-up tags usually mean the market looks interesting but lacks enough history.",
    href: "/watchlist",
  },
  {
    title: "Use alerts for scored events",
    body: "Alerts are stronger than watchlist candidates. Review severity, confidence, and the reason summary, then open the market detail page for position concentration and trade context.",
    href: "/alerts",
  },
] satisfies Array<{ title: string; body: string; href: Route }>;

export default function GuidePage() {
  return (
    <AppShell currentPath="/guide">
      <section className="space-y-6">
        <SectionHeader
          eyebrow="Guide"
          title="How to use the scanner"
          description="This console is built for fast review: check freshness first, narrow the market set, inspect detail pages, and only trust signals that have enough history and context behind them."
        />
        <div className="grid gap-4 lg:grid-cols-2">
          {workflow.map((step, index) => (
            <Card key={step.title}>
              <CardHeader>
                <div className="flex items-center gap-3">
                  <Badge className="border-accent/30 bg-accent/10 text-accent">{`Step ${index + 1}`}</Badge>
                  <CardTitle>{step.title}</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm leading-6 text-slate-600">{step.body}</p>
                <Link href={step.href} className="text-sm font-medium text-accent hover:text-slate-950">
                  Open page
                </Link>
              </CardContent>
            </Card>
          ))}
        </div>
        <Card>
          <CardHeader>
            <CardTitle>What the main fields mean</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2">
            <div className="rounded-2xl border border-line px-4 py-3">
              <div className="text-sm font-semibold text-slate-950">Open / Closed / Accepting orders</div>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                A market can still be marked active in source data while also being closed. `Accepting orders` is useful because it tells you whether the book is live right now.
              </p>
            </div>
            <div className="rounded-2xl border border-line px-4 py-3">
              <div className="text-sm font-semibold text-slate-950">End date vs closed time</div>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                `End date` is the scheduled cutoff when available. `Closed time` is the actual close timestamp recorded by Polymarket for resolved or halted markets.
              </p>
            </div>
            <div className="rounded-2xl border border-line px-4 py-3">
              <div className="text-sm font-semibold text-slate-950">Top-5 seen share</div>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                This is concentration among the top five observed wallets in the holder snapshot. Higher values usually mean thinner ownership and more manipulation risk.
              </p>
            </div>
            <div className="rounded-2xl border border-line px-4 py-3">
              <div className="text-sm font-semibold text-slate-950">Token and reward fields</div>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                The detail page now exposes the yes and no CLOB token IDs plus the ERC reward asset address when the market has a reward program attached.
              </p>
            </div>
          </CardContent>
        </Card>
      </section>
    </AppShell>
  );
}
