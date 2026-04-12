import { AppShell } from "@/components/app-shell";
import { MarketsTable } from "@/components/markets-table";
import { SectionHeader } from "@/components/section-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getMarkets } from "@/lib/api";

const selectClassName =
  "h-10 rounded-xl border border-line bg-white px-3 text-sm text-slate-700 shadow-sm outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/15";

export default async function MarketsPage({
  searchParams,
}: {
  searchParams: Promise<{
    search?: string;
    status?: string;
    history?: string;
    watchlist_only?: string;
    sort?: string;
  }>;
}) {
  const params = await searchParams;
  const search = params.search ?? "";
  const status = params.status ?? "open";
  const history = params.history ?? "";
  const watchlistOnly = params.watchlist_only === "true";
  const sort = params.sort ?? "watchlist_desc";
  const markets = await getMarkets({
    search,
    status,
    history,
    watchlistOnly,
    sort,
  });

  return (
    <AppShell currentPath="/markets">
      <section className="space-y-6">
        <SectionHeader
          eyebrow="Markets"
          title="Market explorer"
          description="Filter by status, history coverage, and watchlist presence, then sort by liquidity proxies like price concentration, holder coverage, or end date before drilling into a market."
        />
        <Card>
          <CardHeader>
            <CardTitle>Filters and Sort</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="grid gap-3 md:grid-cols-2 xl:grid-cols-[minmax(0,1.4fr)_repeat(4,minmax(0,0.7fr))_auto]">
              <Input name="search" defaultValue={search} placeholder="Search by title or category" />
              <select name="status" defaultValue={status} className={selectClassName}>
                <option value="open">Open markets</option>
                <option value="closed">Closed markets</option>
                <option value="archived">Archived markets</option>
                <option value="all">All discovered markets</option>
              </select>
              <select name="history" defaultValue={history} className={selectClassName}>
                <option value="">Any history</option>
                <option value="6h">6h ready</option>
                <option value="24h">24h ready</option>
                <option value="72h">72h ready</option>
              </select>
              <select name="watchlist_only" defaultValue={watchlistOnly ? "true" : "false"} className={selectClassName}>
                <option value="false">All markets</option>
                <option value="true">Watchlist only</option>
              </select>
              <select name="sort" defaultValue={sort} className={selectClassName}>
                <option value="watchlist_desc">Watchlist first</option>
                <option value="latest_snapshot_desc">Latest snapshot</option>
                <option value="yes_price_desc">Yes price high to low</option>
                <option value="yes_price_asc">Yes price low to high</option>
                <option value="top5_desc">Top-5 concentration</option>
                <option value="holders_desc">Observed holders</option>
                <option value="end_date_asc">Ending soonest</option>
                <option value="end_date_desc">Ending latest</option>
                <option value="title_asc">Title A-Z</option>
              </select>
              <button className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white" type="submit">
                Apply
              </button>
            </form>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{markets.total} Markets</CardTitle>
          </CardHeader>
          <CardContent>
            <MarketsTable data={markets.items} />
          </CardContent>
        </Card>
      </section>
    </AppShell>
  );
}
