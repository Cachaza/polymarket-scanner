"use client";

import Link from "next/link";
import { ColumnDef, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";

import { Badge } from "@/components/ui/badge";
import { Table, TBody, TD, TH, THead } from "@/components/ui/table";
import type { MarketsResponse } from "@/lib/api";
import { fmtDateTime, fmtNumber, fmtPercent } from "@/lib/utils";

type MarketRow = MarketsResponse["items"][number];

const columns: ColumnDef<MarketRow>[] = [
  {
    accessorKey: "title",
    header: "Market",
    cell: ({ row }) => (
      <div className="space-y-1">
        <Link href={`/markets/${row.original.condition_id}`} className="font-medium text-slate-950 hover:text-accent">
          {row.original.title}
        </Link>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="uppercase tracking-[0.14em] text-muted">{row.original.category ?? "Uncategorized"}</span>
          {row.original.market_url ? (
            <a href={row.original.market_url} target="_blank" rel="noreferrer" className="font-medium text-accent hover:text-slate-950">
              Open on Polymarket
            </a>
          ) : null}
        </div>
      </div>
    ),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => (
      <div className="space-y-2">
        <div className="flex flex-wrap gap-1">
          <Badge className={row.original.closed ? "border-slate-300 bg-slate-100 text-slate-700" : "border-good/30 bg-good/10 text-good"}>
            {row.original.closed ? "Closed" : "Open"}
          </Badge>
          {row.original.accepting_orders === true ? <Badge className="border-accent/30 bg-accent/10 text-accent">Accepting orders</Badge> : null}
          {row.original.accepting_orders === false && !row.original.closed ? <Badge>Orders off</Badge> : null}
        </div>
        <div className="text-xs text-muted">Ends {fmtDateTime(row.original.end_date)}</div>
      </div>
    ),
  },
  {
    accessorKey: "current_yes_price",
    header: "Yes",
    cell: ({ row }) => <span className="font-mono">{fmtNumber(row.original.current_yes_price, 3)}</span>,
  },
  {
    accessorKey: "yes_top5_seen_share",
    header: "Top-5 Seen",
    cell: ({ row }) => <span className="font-mono">{fmtPercent(row.original.yes_top5_seen_share, 1)}</span>,
  },
  {
    accessorKey: "history",
    header: "History",
    cell: ({ row }) => (
      <div className="flex flex-wrap gap-1">
        <Badge className={row.original.history_ready_6h ? "border-good/30 bg-good/10 text-good" : ""}>6h</Badge>
        <Badge className={row.original.history_ready_24h ? "border-good/30 bg-good/10 text-good" : ""}>24h</Badge>
        <Badge className={row.original.history_ready_72h ? "border-good/30 bg-good/10 text-good" : ""}>72h</Badge>
      </div>
    ),
  },
  {
    accessorKey: "watchlist_flag",
    header: "Flags",
    cell: ({ row }) => (
      <div className="flex flex-wrap gap-1">
        {row.original.watchlist_flag ? <Badge className="border-warn/30 bg-warn/10 text-warn">Watchlist</Badge> : null}
        {row.original.trade_enriched ? <Badge className="border-accent/30 bg-accent/10 text-accent">Trades</Badge> : null}
        {row.original.warmup_only ? <Badge>Warm-up</Badge> : null}
      </div>
    ),
  },
  {
    accessorKey: "latest_snapshot_ts",
    header: "Latest Snapshot",
    cell: ({ row }) => <span className="font-mono text-xs">{fmtDateTime(row.original.latest_snapshot_ts)}</span>,
  },
];

export function MarketsTable({ data }: { data: MarketRow[] }) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="overflow-x-auto">
      <Table>
        <THead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <TH key={header.id}>{flexRender(header.column.columnDef.header, header.getContext())}</TH>
              ))}
            </tr>
          ))}
        </THead>
        <TBody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id} className="hover:bg-slate-50/80">
              {row.getVisibleCells().map((cell) => (
                <TD key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TD>
              ))}
            </tr>
          ))}
        </TBody>
      </Table>
    </div>
  );
}
