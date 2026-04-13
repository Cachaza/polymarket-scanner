import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import { SectionHeader } from "@/components/section-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getAlerts } from "@/lib/api";
import { fmtDateTime, fmtNumber } from "@/lib/utils";

export default async function AlertsPage() {
  const alerts = await getAlerts();

  return (
    <AppShell currentPath="/alerts">
      <section className="space-y-6">
        <SectionHeader
          eyebrow="Alerts"
          title="Alert feed and component breakdowns"
          description="Review raw scored alerts here, then use the recommendations page as the actual action layer for deciding whether to consider a YES entry, wait, or review settled outcomes."
        />
        <Card>
          <CardHeader>
            <CardTitle>{alerts.total} Alerts</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {alerts.items.length === 0 ? (
              <EmptyState
                title="No alerts fired yet"
                description="The current dataset still has no scored alerts. This zero-state is intentional so the console remains usable during warm-up."
              />
            ) : (
              alerts.items.map((alert) => (
                <div key={alert.id} className="rounded-2xl border border-line px-4 py-4">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-2">
                      <Link href={`/markets/${alert.condition_id}`} className="text-lg font-medium hover:text-accent">
                        {alert.market_title ?? alert.condition_id}
                      </Link>
                      <p className="text-sm text-slate-600">{alert.reason_summary}</p>
                      <div className="flex flex-wrap gap-2">
                        <Badge className="border-bad/30 bg-bad/10 text-bad">{alert.severity ?? "n/a"}</Badge>
                        <Badge className="border-accent/30 bg-accent/10 text-accent">{alert.confidence ?? "n/a"}</Badge>
                        <Badge>{alert.action_label ?? "review"}</Badge>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                      <div className="rounded-xl bg-slate-50 px-3 py-2">
                        <div className="font-mono text-lg">{fmtNumber(alert.score_total, 2)}</div>
                        <div className="text-xs uppercase tracking-[0.14em] text-muted">Total</div>
                      </div>
                      <div className="rounded-xl bg-slate-50 px-3 py-2">
                        <div className="font-mono text-lg">{fmtNumber(alert.score_price_anomaly, 1)}</div>
                        <div className="text-xs uppercase tracking-[0.14em] text-muted">Price</div>
                      </div>
                      <div className="rounded-xl bg-slate-50 px-3 py-2">
                        <div className="font-mono text-lg">{fmtNumber(alert.score_holder_concentration, 1)}</div>
                        <div className="text-xs uppercase tracking-[0.14em] text-muted">Holder</div>
                      </div>
                      <div className="rounded-xl bg-slate-50 px-3 py-2">
                        <div className="font-mono text-lg">{fmtNumber(alert.score_wallet_quality + alert.score_trade_flow, 1)}</div>
                        <div className="text-xs uppercase tracking-[0.14em] text-muted">Flow + Wallet</div>
                      </div>
                    </div>
                  </div>
                  <div className="mt-4 text-xs uppercase tracking-[0.14em] text-muted">{fmtDateTime(alert.alert_ts)}</div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </section>
    </AppShell>
  );
}
