import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import { SectionHeader } from "@/components/section-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getWatchlist } from "@/lib/api";
import { fmtDateTime, fmtNumber, fmtPercent } from "@/lib/utils";

export default async function WatchlistPage() {
  const [historyReady, warmup] = await Promise.all([getWatchlist(false), getWatchlist(true)]);

  return (
    <AppShell currentPath="/watchlist">
      <section className="space-y-6">
        <SectionHeader
          eyebrow="Watchlist"
          title="Persisted watchlist candidates"
          description="Track which scanner-scope markets hit the watchlist heuristics on the latest cycle, separated between history-ready candidates and warm-up candidates that still need time."
        />
        <div className="grid gap-4 xl:grid-cols-2">
          {[
            { title: "History-ready", data: historyReady },
            { title: "Warm-up only", data: warmup },
          ].map((group) => (
            <Card key={group.title}>
              <CardHeader>
                <CardTitle>{group.title}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {group.data.items.length === 0 ? (
                  <EmptyState title={`No ${group.title.toLowerCase()} candidates`} description="The latest watchlist cycle does not have items in this bucket yet." />
                ) : (
                  group.data.items.map((item) => (
                    <div key={item.condition_id} className="rounded-2xl border border-line px-4 py-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <a href={item.market_url ?? "#"} target="_blank" rel="noreferrer" className="font-medium hover:text-accent">
                            {item.market_title}
                          </a>
                          <p className="mt-1 text-sm text-slate-600">{item.reason_summary}</p>
                        </div>
                        <div className="text-right">
                          <div className="font-mono text-base font-semibold">{fmtNumber(item.current_yes_price, 3)}</div>
                          <div className="font-mono text-xs text-muted">{fmtDateTime(item.snapshot_ts)}</div>
                        </div>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Badge className="border-line bg-slate-50 text-slate-700">Top-5 {fmtPercent(item.yes_top5_seen_share, 1)}</Badge>
                        {item.price_anomaly_hit ? <Badge className="border-bad/30 bg-bad/10 text-bad">Price anomaly</Badge> : null}
                        {item.holder_concentration_hit ? <Badge className="border-warn/30 bg-warn/10 text-warn">Concentration</Badge> : null}
                        {item.wallet_quality_hit ? <Badge className="border-good/30 bg-good/10 text-good">Wallet quality</Badge> : null}
                        {item.trade_enriched ? <Badge className="border-accent/30 bg-accent/10 text-accent">Trade enriched</Badge> : null}
                      </div>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </AppShell>
  );
}
