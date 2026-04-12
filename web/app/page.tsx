import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import { SectionHeader } from "@/components/section-header";
import { StatCard } from "@/components/stat-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getAlerts, getOverview, getSystem, getWatchlist } from "@/lib/api";
import { fmtDateTime, fmtNumber } from "@/lib/utils";

export default async function OverviewPage() {
  const [overview, watchlist, alerts, system] = await Promise.all([
    getOverview(),
    getWatchlist(),
    getAlerts(),
    getSystem(),
  ]);

  return (
    <AppShell currentPath="/">
      <section className="space-y-6">
        <SectionHeader
          eyebrow="Overview"
          title="Scanner health and review queue"
          description="Start here to see freshness, scope, history coverage, and the current review queue before drilling into markets, watchlist candidates, or alert history."
        />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Active Scope" value={overview.active_scanner_scope} hint={`${overview.markets_discovered} discovered markets in DB`} />
          <StatCard label="Latest Snapshot" value={fmtDateTime(overview.latest_snapshot_ts)} hint={`DB age ${overview.db_age}`} />
          <StatCard label="Watchlist" value={overview.watchlist_candidates} hint={`Latest cycle ${fmtDateTime(overview.latest_watchlist_snapshot_ts)}`} />
          <StatCard label="Alerts" value={overview.alerts_count} hint="Current alert table count" />
        </div>
        <div className="grid gap-4 lg:grid-cols-[1.25fr_0.75fr]">
          <Card>
            <CardHeader>
              <CardTitle>Current Watchlist</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {watchlist.items.length === 0 ? (
                <EmptyState
                  title="No persisted watchlist candidates yet"
                  description="Run a fresh snapshot cycle after the migration to start recording watchlist history."
                />
              ) : (
                watchlist.items.slice(0, 6).map((item) => (
                  <div key={item.condition_id} className="rounded-2xl border border-line px-4 py-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <Link href={`/markets/${item.condition_id}`} className="font-medium text-slate-950 hover:text-accent">
                          {item.market_title}
                        </Link>
                        <p className="mt-1 text-sm text-slate-600">{item.reason_summary}</p>
                      </div>
                      <div className="text-right">
                        <div className="font-mono text-base font-semibold">{fmtNumber(item.current_yes_price, 3)}</div>
                        <p className="text-xs uppercase tracking-[0.14em] text-muted">{fmtDateTime(item.snapshot_ts)}</p>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {item.price_anomaly_hit ? <Badge className="border-bad/30 bg-bad/10 text-bad">Price anomaly</Badge> : null}
                      {item.holder_concentration_hit ? <Badge className="border-warn/30 bg-warn/10 text-warn">Concentration</Badge> : null}
                      {item.wallet_quality_hit ? <Badge className="border-good/30 bg-good/10 text-good">Wallet quality</Badge> : null}
                      {item.trade_enriched ? <Badge className="border-accent/30 bg-accent/10 text-accent">Trade enriched</Badge> : null}
                      {item.warmup_only ? <Badge>Warm-up</Badge> : null}
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>System Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl border border-line px-4 py-3">
                  <div className="font-mono text-2xl font-semibold">{overview.markets_with_enough_6h_history}</div>
                  <p className="text-sm text-slate-600">Markets with 6h history</p>
                </div>
                <div className="rounded-2xl border border-line px-4 py-3">
                  <div className="font-mono text-2xl font-semibold">{overview.backtestable_alerts_24h}</div>
                  <p className="text-sm text-slate-600">Backtestable alerts 24h</p>
                </div>
              </div>
              {system.recent_job_runs.length === 0 ? (
                <EmptyState title="No job history yet" description="Job run records will appear after the tracked commands are executed." />
              ) : (
                system.recent_job_runs.slice(0, 5).map((job) => (
                  <div key={job.id} className="flex items-center justify-between rounded-2xl border border-line px-4 py-3">
                    <div>
                      <p className="font-medium">{job.job_name}</p>
                      <p className="text-sm text-slate-600">{fmtDateTime(job.started_at)}</p>
                    </div>
                    <Badge className={job.status === "completed" ? "border-good/30 bg-good/10 text-good" : "border-bad/30 bg-bad/10 text-bad"}>
                      {job.status}
                    </Badge>
                  </div>
                ))
              )}
              <div className="rounded-2xl border border-line bg-slate-50 px-4 py-3 text-sm text-slate-600">
                Backtest CSV freshness: <span className="font-mono text-slate-950">{fmtDateTime(system.backtest_updated_at)}</span>
              </div>
            </CardContent>
          </Card>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Recent Alerts</CardTitle>
          </CardHeader>
          <CardContent>
            {alerts.items.length === 0 ? (
              <EmptyState
                title="Alerts are empty on the current dataset"
                description="That is expected while the database is still warming up. The page still provides a clean review surface once scored alerts start landing."
              />
            ) : null}
          </CardContent>
        </Card>
      </section>
    </AppShell>
  );
}
