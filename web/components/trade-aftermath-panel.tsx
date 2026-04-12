"use client";

import { Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { EmptyState } from "@/components/empty-state";
import { Badge } from "@/components/ui/badge";
import type { MarketTradeAftermathResponse } from "@/lib/api";
import { fmtDateTime, fmtNumber, fmtSignedPercent, shortenAddress } from "@/lib/utils";

type AftermathItem = MarketTradeAftermathResponse["items"][number];

function outcomeTone(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "border-slate-300 bg-slate-100 text-slate-700";
  }
  if (value > 0) {
    return "border-good/30 bg-good/10 text-good";
  }
  if (value < 0) {
    return "border-bad/30 bg-bad/10 text-bad";
  }
  return "border-slate-300 bg-slate-100 text-slate-700";
}

function HorizonChip({ item, hours }: { item: AftermathItem; hours: number }) {
  const horizon = item.horizons.find((entry) => entry.target_hours === hours);
  return (
    <div className="rounded-2xl border border-line px-4 py-3">
      <div className="text-xs uppercase tracking-[0.14em] text-muted">{hours}h after</div>
      <div className="mt-2 font-mono text-lg">{fmtSignedPercent(horizon?.outcome_return ?? null, 1)}</div>
      <p className="mt-1 text-xs text-slate-600">
        {horizon?.snapshot_ts ? `${fmtDateTime(horizon.snapshot_ts)} (${fmtNumber(horizon.observed_hours_after_trade ?? null, 1)}h)` : "No snapshot yet"}
      </p>
    </div>
  );
}

function AftermathChart({ item }: { item: AftermathItem }) {
  if (item.surrounding_points.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-line bg-slate-50 px-4 py-6 text-sm text-slate-600">
        No snapshot window is available around this trade yet.
      </div>
    );
  }

  return (
    <div className="h-56 w-full">
      <ResponsiveContainer>
        <LineChart data={item.surrounding_points}>
          <XAxis
            type="number"
            dataKey="relative_hours"
            tick={{ fontSize: 11 }}
            tickFormatter={(value: number) => `${value}h`}
            domain={["dataMin", "dataMax"]}
          />
          <YAxis tick={{ fontSize: 11 }} domain={[0, 1]} />
          <Tooltip
            formatter={(value) => fmtNumber(typeof value === "number" ? value : null, 3)}
            labelFormatter={(value) => `${typeof value === "number" ? value.toFixed(2) : value}h from trade`}
          />
          <ReferenceLine x={0} stroke="hsl(12 76% 48%)" strokeDasharray="4 4" />
          <Line dataKey="yes_price" stroke="hsl(205 68% 42%)" dot={false} strokeWidth={2.4} />
          <Line dataKey="no_price" stroke="hsl(28 92% 48%)" dot={false} strokeWidth={2.2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function TradeAftermathPanel({ data }: { data: MarketTradeAftermathResponse }) {
  if (data.items.length === 0) {
    return (
      <EmptyState
        title="No large buys matched the filter"
        description="This panel looks for higher-notional buy trades, then maps them to the stored yes/no snapshots before and after entry."
      />
    );
  }

  return (
    <div className="space-y-4">
      {data.items.map((item) => (
        <div key={item.trade_key} className="rounded-[28px] border border-line bg-white/80 px-5 py-5 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <Badge className="border-accent/30 bg-accent/10 text-accent">{(item.side ?? "trade").toUpperCase()}</Badge>
                <Badge>{item.outcome ?? "n/a"}</Badge>
                <Badge className={outcomeTone(item.current_outcome_return)}>{fmtSignedPercent(item.current_outcome_return, 1)} now</Badge>
              </div>
              <div className="font-medium text-slate-900">{shortenAddress(item.wallet_address)}</div>
              <div className="font-mono text-xs text-muted">{fmtDateTime(item.trade_ts)}</div>
            </div>
            <div className="text-right">
              <div className="font-mono text-2xl">{fmtNumber(item.notional, 0)}</div>
              <p className="text-sm text-slate-600">
                {fmtNumber(item.price, 3)} x {fmtNumber(item.size, 2)}
              </p>
            </div>
          </div>

          <div className="mt-4 grid gap-3 lg:grid-cols-4">
            <div className="rounded-2xl border border-line px-4 py-3">
              <div className="text-xs uppercase tracking-[0.14em] text-muted">Entry snapshot</div>
              <div className="mt-2 font-mono text-lg">
                {fmtNumber(item.entry_yes_price, 3)} / {fmtNumber(item.entry_no_price, 3)}
              </div>
              <p className="mt-1 text-xs text-slate-600">
                {item.entry_snapshot_ts ? `${fmtDateTime(item.entry_snapshot_ts)} (${fmtNumber(item.entry_snapshot_lag_minutes, 1)}m lag)` : "No snapshot before trade"}
              </p>
            </div>
            <div className="rounded-2xl border border-line px-4 py-3">
              <div className="text-xs uppercase tracking-[0.14em] text-muted">Current market</div>
              <div className="mt-2 font-mono text-lg">
                {fmtNumber(item.current_yes_price, 3)} / {fmtNumber(item.current_no_price, 3)}
              </div>
              <p className="mt-1 text-xs text-slate-600">{fmtDateTime(item.current_snapshot_ts)}</p>
            </div>
            <div className="rounded-2xl border border-line px-4 py-3">
              <div className="text-xs uppercase tracking-[0.14em] text-muted">Wallet quality</div>
              <div className="mt-2 font-mono text-lg">{fmtNumber(item.politics_score, 1)}</div>
              <p className="mt-1 text-xs text-slate-600">Politics rank {fmtNumber(item.politics_pnl_rank, 0)}</p>
            </div>
            <div className="rounded-2xl border border-line px-4 py-3">
              <div className="text-xs uppercase tracking-[0.14em] text-muted">Position now</div>
              <div className="mt-2 font-mono text-lg">{fmtSignedPercent(item.current_outcome_return, 1)}</div>
              <p className="mt-1 text-xs text-slate-600">
                {item.outcome ?? "n/a"} at {fmtNumber(item.current_outcome_price, 3)}
              </p>
            </div>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <HorizonChip item={item} hours={6} />
            <HorizonChip item={item} hours={24} />
            <HorizonChip item={item} hours={72} />
          </div>

          <div className="mt-5">
            <div className="mb-2 flex items-center justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-[0.14em] text-muted">Yes / No around entry</div>
                <p className="text-sm text-slate-600">Blue is `YES`, orange is `NO`, and the dashed line marks the trade timestamp.</p>
              </div>
            </div>
            <AftermathChart item={item} />
          </div>
        </div>
      ))}
    </div>
  );
}
