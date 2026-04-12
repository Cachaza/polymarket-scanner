import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import { SectionHeader } from "@/components/section-header";
import { StatCard } from "@/components/stat-card";
import { SystemActionsPanel } from "@/components/system-actions-panel";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getSystem } from "@/lib/api";
import { fmtDateTime } from "@/lib/utils";

export default async function SystemPage() {
  const system = await getSystem();

  return (
    <AppShell currentPath="/system">
      <section className="space-y-6">
        <SectionHeader
          eyebrow="System"
          title="Operational diagnostics and job history"
          description="Track snapshot freshness, history coverage, backtest freshness, and the recent tracked execution log for scanner jobs."
        />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatCard label="DB Age" value={system.overview.db_age} />
          <StatCard label="Latest Snapshot" value={fmtDateTime(system.overview.latest_snapshot_ts)} />
          <StatCard label="6h Ready" value={system.overview.markets_with_enough_6h_history} />
          <StatCard label="Backtest CSV" value={fmtDateTime(system.backtest_updated_at)} />
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Latent Backtest CSV" value={fmtDateTime(system.latent_backtest_updated_at)} />
          <StatCard label="Alert Backtest File" value={system.backtest_exists ? "Present" : "Missing"} />
          <StatCard label="Latent Backtest File" value={system.latent_backtest_exists ? "Present" : "Missing"} />
          <StatCard label="24h Ready" value={system.overview.markets_with_enough_24h_history} />
        </div>
        <SystemActionsPanel />
        <Card>
          <CardHeader>
            <CardTitle>Recent Job Runs</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {system.recent_job_runs.length === 0 ? (
              <EmptyState title="No tracked jobs yet" description="Run discover, snapshot, score-alerts, refresh-leaderboard, or backtest to populate this log." />
            ) : (
              system.recent_job_runs.map((job) => (
                <div key={job.id} className="rounded-2xl border border-line px-4 py-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="font-medium">{job.job_name}</div>
                      <div className="font-mono text-xs text-muted">{fmtDateTime(job.started_at)} → {fmtDateTime(job.finished_at)}</div>
                    </div>
                    <Badge className={job.status === "completed" ? "border-good/30 bg-good/10 text-good" : "border-bad/30 bg-bad/10 text-bad"}>
                      {job.status}
                    </Badge>
                  </div>
                  <pre className="mt-3 overflow-x-auto rounded-xl bg-slate-50 p-3 font-mono text-xs text-slate-700">
                    {JSON.stringify(job.meta, null, 2)}
                  </pre>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </section>
    </AppShell>
  );
}
