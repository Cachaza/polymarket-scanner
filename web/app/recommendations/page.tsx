import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import { SectionHeader } from "@/components/section-header";
import { StatCard } from "@/components/stat-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getRecommendations } from "@/lib/api";
import { fmtDateTime, fmtNumber, fmtSignedPercent } from "@/lib/utils";

function recommendationTone(value: string) {
  if (value === "consider_yes") return "border-good/30 bg-good/10 text-good";
  if (value === "consider_no") return "border-good/30 bg-good/10 text-good";
  if (value === "watch_yes") return "border-accent/30 bg-accent/10 text-accent";
  if (value === "watch_no") return "border-accent/30 bg-accent/10 text-accent";
  return "border-warn/30 bg-warn/10 text-warn";
}

function verdictTone(value: string | null) {
  if (value === "good_call") return "border-good/30 bg-good/10 text-good";
  if (value === "bad_call") return "border-bad/30 bg-bad/10 text-bad";
  return "border-line bg-slate-50 text-slate-700";
}

function recommendationLabel(value: string) {
  if (value === "consider_yes") return "Consider YES";
  if (value === "consider_no") return "Consider NO";
  if (value === "watch_yes") return "Watch YES";
  if (value === "watch_no") return "Watch NO";
  return "Wait for history";
}

function verdictLabel(value: string | null) {
  if (value === "good_call") return "Good call";
  if (value === "bad_call") return "Bad call";
  if (value === "flat_call") return "Flat result";
  return "Pending";
}

export default async function RecommendationsPage() {
  const recommendations = await getRecommendations();
  const openItems = recommendations.items.filter((item) => item.status !== "settled");
  const settledItems = recommendations.items.filter((item) => item.status === "settled");

  return (
    <AppShell currentPath="/recommendations">
      <section className="space-y-6">
        <SectionHeader
          eyebrow="Recommendations"
          title="Decision queue with feedback"
          description="Use alerts as raw telemetry and this page as the action layer. Open items tell you whether to consider an entry or wait, and settled items track whether the thesis ended up being right."
        />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Total ideas" value={recommendations.total} hint="Latest alert or watchlist thesis per market" />
          <StatCard label="Actionable" value={recommendations.actionable} hint="Strong enough to consider an entry now" />
          <StatCard label="Monitoring" value={recommendations.monitoring} hint="Interesting, but not ready to act yet" />
          <StatCard label="Settled" value={recommendations.settled} hint="Closed markets with feedback on the call" />
        </div>
        <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
          <Card>
            <CardHeader>
              <CardTitle>Open Queue</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {openItems.length === 0 ? (
                <EmptyState title="No open ideas right now" description="Once alerts or watchlist candidates appear, this queue will turn them into actionable or waiting recommendations." />
              ) : (
                openItems.map((item) => (
                  <div key={item.condition_id} className="rounded-2xl border border-line px-4 py-4">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div className="space-y-2">
                        <Link href={`/markets/${item.condition_id}`} className="text-lg font-medium text-slate-950 hover:text-accent">
                          {item.market_title}
                        </Link>
                        <p className="text-sm text-slate-600">{item.reason_summary}</p>
                        <div className="flex flex-wrap gap-2">
                          <Badge className={recommendationTone(item.recommendation)}>{recommendationLabel(item.recommendation)}</Badge>
                          <Badge>{item.source}</Badge>
                          <Badge>{item.side}</Badge>
                          {item.confidence ? <Badge className="border-accent/30 bg-accent/10 text-accent">{item.confidence}</Badge> : null}
                          {item.severity ? <Badge className="border-bad/30 bg-bad/10 text-bad">{item.severity}</Badge> : null}
                          {item.trade_enriched ? <Badge className="border-line bg-slate-50 text-slate-700">Trade enriched</Badge> : null}
                          {item.warmup_only ? <Badge className="border-warn/30 bg-warn/10 text-warn">Warm-up</Badge> : null}
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                        <div className="rounded-xl bg-slate-50 px-3 py-2">
                          <div className="font-mono text-lg">{fmtNumber(item.conviction_score, 1)}</div>
                          <div className="text-xs uppercase tracking-[0.14em] text-muted">Score</div>
                        </div>
                        <div className="rounded-xl bg-slate-50 px-3 py-2">
                          <div className="font-mono text-lg">{fmtNumber(item.entry_price, 3)}</div>
                          <div className="text-xs uppercase tracking-[0.14em] text-muted">Entry</div>
                        </div>
                        <div className="rounded-xl bg-slate-50 px-3 py-2">
                          <div className="font-mono text-lg">{fmtNumber(item.current_price, 3)}</div>
                          <div className="text-xs uppercase tracking-[0.14em] text-muted">Now</div>
                        </div>
                        <div className="rounded-xl bg-slate-50 px-3 py-2">
                          <div className="font-mono text-lg">{fmtSignedPercent(item.current_return, 1)}</div>
                          <div className="text-xs uppercase tracking-[0.14em] text-muted">P/L</div>
                        </div>
                      </div>
                    </div>
                    <div className="mt-4 flex flex-wrap items-center gap-3 text-xs uppercase tracking-[0.14em] text-muted">
                      <span>Entry {fmtDateTime(item.entry_ts)}</span>
                      <span>Snapshot {fmtDateTime(item.latest_snapshot_ts)}</span>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Settled Feedback</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {settledItems.length === 0 ? (
                <EmptyState title="No settled ideas yet" description="Closed markets will move here so you can see whether the thesis was actually right or wrong." />
              ) : (
                settledItems.map((item) => (
                  <div key={item.condition_id} className="rounded-2xl border border-line px-4 py-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <Link href={`/markets/${item.condition_id}`} className="font-medium text-slate-950 hover:text-accent">
                          {item.market_title}
                        </Link>
                        <p className="mt-1 text-sm text-slate-600">{item.reason_summary}</p>
                      </div>
                      <Badge className={verdictTone(item.outcome_verdict)}>{verdictLabel(item.outcome_verdict)}</Badge>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Badge className={recommendationTone(item.recommendation)}>{recommendationLabel(item.recommendation)}</Badge>
                      <Badge>{item.source}</Badge>
                      {item.confidence ? <Badge>{item.confidence}</Badge> : null}
                    </div>
                    <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
                      <div className="rounded-xl bg-slate-50 px-3 py-2">
                        <div className="font-mono text-lg">{fmtNumber(item.entry_price, 3)}</div>
                        <div className="text-xs uppercase tracking-[0.14em] text-muted">Entry</div>
                      </div>
                      <div className="rounded-xl bg-slate-50 px-3 py-2">
                        <div className="font-mono text-lg">{fmtNumber(item.final_price, 3)}</div>
                        <div className="text-xs uppercase tracking-[0.14em] text-muted">Final</div>
                      </div>
                      <div className="rounded-xl bg-slate-50 px-3 py-2">
                        <div className="font-mono text-lg">{fmtSignedPercent(item.outcome_return, 1)}</div>
                        <div className="text-xs uppercase tracking-[0.14em] text-muted">Outcome</div>
                      </div>
                      <div className="rounded-xl bg-slate-50 px-3 py-2">
                        <div className="font-mono text-lg">{fmtDateTime(item.closed_time)}</div>
                        <div className="text-xs uppercase tracking-[0.14em] text-muted">Closed</div>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      </section>
    </AppShell>
  );
}
