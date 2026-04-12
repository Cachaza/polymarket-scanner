import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import { SectionHeader } from "@/components/section-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getBacktests, getLatentBacktests } from "@/lib/api";
import { fmtDateTime, fmtNumber } from "@/lib/utils";

export default async function ResearchPage() {
  const [backtests, latentBacktests] = await Promise.all([getBacktests(), getLatentBacktests()]);

  return (
    <AppShell currentPath="/research">
      <section className="space-y-6">
        <SectionHeader
          eyebrow="Research"
          title="Backtest feedback loop"
          description="Compare the standard alert backtest with the latent strong-wallet entry research export, then iterate on the settings from the system panel."
        />
        <div className="grid gap-4 xl:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Alert Backtest File</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-3">
              <div className="rounded-2xl border border-line px-4 py-3">
                <div className="font-mono text-lg">{backtests.exists ? "Present" : "Missing"}</div>
                <p className="text-sm text-slate-600">{backtests.csv_path}</p>
              </div>
              <div className="rounded-2xl border border-line px-4 py-3">
                <div className="font-mono text-lg">{fmtDateTime(backtests.updated_at)}</div>
                <p className="text-sm text-slate-600">Last updated</p>
              </div>
              <div className="rounded-2xl border border-line px-4 py-3">
                <div className="font-mono text-lg">{backtests.total_rows}</div>
                <p className="text-sm text-slate-600">Rows available</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Latent Entry Backtest File</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-3">
              <div className="rounded-2xl border border-line px-4 py-3">
                <div className="font-mono text-lg">{latentBacktests.exists ? "Present" : "Missing"}</div>
                <p className="text-sm text-slate-600">{latentBacktests.csv_path}</p>
              </div>
              <div className="rounded-2xl border border-line px-4 py-3">
                <div className="font-mono text-lg">{fmtDateTime(latentBacktests.updated_at)}</div>
                <p className="text-sm text-slate-600">Last updated</p>
              </div>
              <div className="rounded-2xl border border-line px-4 py-3">
                <div className="font-mono text-lg">{latentBacktests.total_rows}</div>
                <p className="text-sm text-slate-600">Rows available</p>
              </div>
            </CardContent>
          </Card>
        </div>
        <div className="grid gap-4 xl:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Alert Score Buckets</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {backtests.score_buckets.length === 0 ? (
                <EmptyState title="No scored outcomes yet" description="Run a backtest after alerts exist to populate score-bucket performance." />
              ) : (
                backtests.score_buckets.map((bucket) => (
                  <div key={bucket.key} className="flex items-center justify-between rounded-2xl border border-line px-4 py-3">
                    <div>
                      <div className="font-medium">{bucket.key}</div>
                      <div className="text-sm text-slate-600">{bucket.count} rows</div>
                    </div>
                    <div className="text-right text-sm">
                      <div className="font-mono">{fmtNumber(bucket.avg_return, 3)} avg</div>
                      <div className="font-mono text-slate-600">{fmtNumber(bucket.positive_rate, 3)} pos</div>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Latent Score Buckets</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {latentBacktests.score_buckets.length === 0 ? (
                <EmptyState title="No latent outcomes yet" description="Run the latent backtest from the system page after trade and snapshot history exists." />
              ) : (
                latentBacktests.score_buckets.map((bucket) => (
                  <div key={bucket.key} className="flex items-center justify-between rounded-2xl border border-line px-4 py-3">
                    <div>
                      <div className="font-medium">{bucket.key}</div>
                      <div className="text-sm text-slate-600">{bucket.count} rows</div>
                    </div>
                    <div className="text-right text-sm">
                      <div className="font-mono">{fmtNumber(bucket.avg_return, 3)} avg</div>
                      <div className="font-mono text-slate-600">{fmtNumber(bucket.positive_rate, 3)} pos</div>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Alert Missing Reasons</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {backtests.missing_reason_buckets.length === 0 ? (
              <EmptyState title="No missing-data analysis yet" description="The current alert backtest export has no populated forward-return rows or missing-reason columns." />
            ) : (
              backtests.missing_reason_buckets.map((bucket) => (
                <div key={bucket.key} className="flex items-center justify-between rounded-2xl border border-line px-4 py-3">
                  <div className="font-medium">{bucket.key}</div>
                  <div className="font-mono">{bucket.count}</div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </section>
    </AppShell>
  );
}
