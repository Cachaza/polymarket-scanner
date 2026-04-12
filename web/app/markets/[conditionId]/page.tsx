import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import { LiveMarketActivity } from "@/components/live-market-activity";
import { SectionHeader } from "@/components/section-header";
import { TimeSeriesChart } from "@/components/timeseries-chart";
import { TradeAftermathPanel } from "@/components/trade-aftermath-panel";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead } from "@/components/ui/table";
import { getAlerts, getMarketDetail, getMarketHolders, getMarketTimeseries, getMarketTradeAftermath, getMarketTrades } from "@/lib/api";
import { fmtDateTime, fmtNumber, fmtPercent, shortenAddress } from "@/lib/utils";

function MetadataRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-line/70 py-2 last:border-b-0">
      <div className="text-xs uppercase tracking-[0.14em] text-muted">{label}</div>
      <div className="max-w-[70%] text-right font-mono text-xs text-slate-700 break-all">{value}</div>
    </div>
  );
}

export default async function MarketDetailPage({
  params,
}: {
  params: Promise<{ conditionId: string }>;
}) {
  const { conditionId } = await params;

  try {
    const [detail, timeseries, holders, trades, tradeAftermath, alerts] = await Promise.all([
      getMarketDetail(conditionId),
      getMarketTimeseries(conditionId),
      getMarketHolders(conditionId),
      getMarketTrades(conditionId),
      getMarketTradeAftermath(conditionId),
      getAlerts(),
    ]);
    const relatedAlerts = alerts.items.filter((item) => item.condition_id === conditionId);

    return (
      <AppShell currentPath="/markets">
        <section className="space-y-6">
          <SectionHeader
            eyebrow="Market Detail"
            title={detail.title}
            description={detail.latest_watchlist_reason_summary ?? "Inspect price, holder concentration, wallet quality, trade flow, and related alert history for this market."}
          />
          <div className="flex flex-wrap gap-2">
            <Badge className="border-accent/30 bg-accent/10 text-accent">{detail.category ?? "Uncategorized"}</Badge>
            {detail.watchlist_flag ? <Badge className="border-warn/30 bg-warn/10 text-warn">Watchlist</Badge> : null}
            {detail.trade_enriched ? <Badge className="border-accent/30 bg-accent/10 text-accent">Trade enriched</Badge> : null}
            {detail.warmup_only ? <Badge>Warm-up</Badge> : null}
            <Badge className={detail.closed ? "border-slate-300 bg-slate-100 text-slate-700" : "border-good/30 bg-good/10 text-good"}>
              {detail.closed ? "Closed" : "Open"}
            </Badge>
            {detail.accepting_orders === true ? <Badge className="border-accent/30 bg-accent/10 text-accent">Accepting orders</Badge> : null}
          </div>
          <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
            <Card>
              <CardHeader>
                <CardTitle>Price and Concentration</CardTitle>
              </CardHeader>
              <CardContent>
                {timeseries.items.length === 0 ? (
                  <EmptyState title="No timeseries yet" description="The scanner has not captured snapshots for this market yet." />
                ) : (
                  <TimeSeriesChart data={timeseries.items} />
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Current State</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl border border-line px-4 py-3">
                  <div className="font-mono text-2xl">{fmtNumber(detail.current_yes_price, 3)}</div>
                  <p className="text-sm text-slate-600">Current yes price</p>
                </div>
                <div className="rounded-2xl border border-line px-4 py-3">
                  <div className="font-mono text-2xl">{fmtPercent(detail.yes_top5_seen_share, 1)}</div>
                  <p className="text-sm text-slate-600">Yes top-5 seen share</p>
                </div>
                <div className="rounded-2xl border border-line px-4 py-3">
                  <div className="font-mono text-2xl">{detail.observed_holder_wallets ?? "n/a"}</div>
                  <p className="text-sm text-slate-600">Observed holder wallets</p>
                </div>
                <div className="rounded-2xl border border-line px-4 py-3">
                  <div className="font-mono text-2xl">{detail.recent_alert_count}</div>
                  <p className="text-sm text-slate-600">Related alerts</p>
                </div>
              </CardContent>
            </Card>
          </div>
          <div className="grid gap-4 xl:grid-cols-[0.8fr_1.2fr]">
            <Card>
              <CardHeader>
                <CardTitle>Polymarket Metadata</CardTitle>
              </CardHeader>
              <CardContent>
                {detail.image_url ? (
                  <div
                    className="mb-4 h-40 rounded-2xl border border-line bg-cover bg-center"
                    style={{ backgroundImage: `linear-gradient(180deg, rgba(15,23,42,0.08), rgba(15,23,42,0.18)), url(${detail.image_url})` }}
                  />
                ) : null}
                <div className="space-y-0">
                  <MetadataRow
                    label="Market URL"
                    value={
                      detail.market_url ? (
                        <a href={detail.market_url} target="_blank" rel="noreferrer" className="font-medium text-accent hover:text-slate-950">
                          {detail.market_url}
                        </a>
                      ) : (
                        "n/a"
                      )
                    }
                  />
                  <MetadataRow label="End date" value={fmtDateTime(detail.end_date)} />
                  <MetadataRow label="Closed time" value={fmtDateTime(detail.closed_time)} />
                  <MetadataRow label="Market ID" value={detail.market_id ?? "n/a"} />
                  <MetadataRow label="Question ID" value={detail.question_id ?? "n/a"} />
                  <MetadataRow label="Yes token" value={detail.yes_token_id ?? "n/a"} />
                  <MetadataRow label="No token" value={detail.no_token_id ?? "n/a"} />
                  <MetadataRow label="Reward asset" value={detail.reward_asset_address ?? "n/a"} />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Operational State</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl border border-line px-4 py-3">
                  <div className="font-mono text-2xl">{detail.active ? "true" : "false"}</div>
                  <p className="text-sm text-slate-600">Active</p>
                </div>
                <div className="rounded-2xl border border-line px-4 py-3">
                  <div className="font-mono text-2xl">{detail.closed ? "true" : "false"}</div>
                  <p className="text-sm text-slate-600">Closed</p>
                </div>
                <div className="rounded-2xl border border-line px-4 py-3">
                  <div className="font-mono text-2xl">{detail.accepting_orders === null ? "n/a" : detail.accepting_orders ? "true" : "false"}</div>
                  <p className="text-sm text-slate-600">Accepting orders</p>
                </div>
                <div className="rounded-2xl border border-line px-4 py-3">
                  <div className="font-mono text-2xl">{detail.archived ? "true" : "false"}</div>
                  <p className="text-sm text-slate-600">Archived</p>
                </div>
              </CardContent>
            </Card>
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Latest Holders</CardTitle>
              </CardHeader>
              <CardContent>
                {holders.items.length === 0 ? (
                  <EmptyState title="No holder snapshot yet" description="Holder rows will appear after the market is included in a snapshot cycle." />
                ) : (
                  <div className="overflow-x-auto">
                    <Table>
                      <THead>
                        <tr>
                          <TH>Wallet</TH>
                          <TH>Amount</TH>
                          <TH>Politics</TH>
                          <TH>Overall</TH>
                        </tr>
                      </THead>
                      <TBody>
                        {holders.items.map((holder) => (
                          <tr key={`${holder.wallet_address}-${holder.token_id}`}>
                            <TD className="font-mono text-xs">{shortenAddress(holder.wallet_address)}</TD>
                            <TD className="font-mono">{fmtNumber(holder.amount, 2)}</TD>
                            <TD className="font-mono">{fmtNumber(holder.politics_score, 1)}</TD>
                            <TD className="font-mono">{fmtNumber(holder.overall_score, 1)}</TD>
                          </tr>
                        ))}
                      </TBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>
            <LiveMarketActivity detail={detail} trades={trades.items} holders={holders.items} />
          </div>
          <Card>
            <CardHeader>
              <CardTitle>Unusual Entry Analysis</CardTitle>
            </CardHeader>
            <CardContent>
              <TradeAftermathPanel data={tradeAftermath} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Related Alerts</CardTitle>
            </CardHeader>
            <CardContent>
              {relatedAlerts.length === 0 ? (
                <EmptyState title="No related alerts" description="This market detail page still renders cleanly even when no scored alerts exist." />
              ) : (
                relatedAlerts.map((alert) => (
                  <div key={alert.id} className="rounded-2xl border border-line px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="font-medium">{alert.reason_summary}</div>
                        <div className="font-mono text-xs text-muted">{fmtDateTime(alert.alert_ts)}</div>
                      </div>
                      <Badge className="border-bad/30 bg-bad/10 text-bad">{alert.severity ?? "n/a"}</Badge>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </section>
      </AppShell>
    );
  } catch {
    notFound();
  }
}
