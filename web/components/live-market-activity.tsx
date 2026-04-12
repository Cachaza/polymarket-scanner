"use client";

import { useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { HoldersResponse, MarketDetail, TradesResponse } from "@/lib/api";
import { fmtDateTime, fmtNumber, shortenAddress } from "@/lib/utils";

const MARKET_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market";
const HEARTBEAT_MS = 10_000;
const RECONNECT_MS = 3_000;

type TradeRow = TradesResponse["items"][number];
type HolderRow = HoldersResponse["items"][number];

type ActivityTrade = {
  id: string;
  tradeTs: string;
  assetId: string | null;
  outcome: string | null;
  side: string | null;
  price: number | null;
  size: number | null;
  notional: number | null;
  txHash: string | null;
  walletAddress: string | null;
  source: "history" | "live";
};

type LiveQuote = {
  bestBid: number | null;
  bestAsk: number | null;
  spread: number | null;
  timestamp: string | null;
};

function parseNumeric(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function normalizeTimestamp(value: string | null | undefined) {
  if (!value) {
    return "";
  }
  if (/^\d+$/.test(value)) {
    return new Date(Number(value)).toISOString();
  }
  if (value.includes("T")) {
    return value;
  }
  return `${value.replace(" ", "T")}Z`;
}

function timestampToMillis(value: string | null | undefined) {
  const normalized = normalizeTimestamp(value);
  const parsed = Date.parse(normalized);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function buildSeedTrades(detail: MarketDetail, trades: TradeRow[]) {
  return trades
    .map<ActivityTrade>((trade) => ({
      id: trade.trade_key,
      tradeTs: normalizeTimestamp(trade.trade_ts),
      assetId:
        trade.outcome === "Yes"
          ? detail.yes_token_id
          : trade.outcome === "No"
            ? detail.no_token_id
            : null,
      outcome: trade.outcome ?? null,
      side: trade.side ? trade.side.toUpperCase() : null,
      price: trade.price ?? null,
      size: trade.size ?? null,
      notional: trade.notional ?? null,
      txHash: trade.tx_hash ?? null,
      walletAddress: trade.wallet_address ?? null,
      source: "history",
    }))
    .sort((left, right) => timestampToMillis(right.tradeTs) - timestampToMillis(left.tradeTs));
}

function PolygonscanLink({
  kind,
  value,
}: {
  kind: "tx" | "address";
  value: string | null | undefined;
}) {
  if (!value) {
    return <span>n/a</span>;
  }

  const href = kind === "tx" ? `https://polygonscan.com/tx/${value}` : `https://polygonscan.com/address/${value}`;
  return (
    <a href={href} target="_blank" rel="noreferrer" className="font-medium text-accent hover:text-slate-950">
      {shortenAddress(value)}
    </a>
  );
}

export function LiveMarketActivity({
  detail,
  trades,
  holders,
}: {
  detail: MarketDetail;
  trades: TradeRow[];
  holders: HolderRow[];
}) {
  const hasAssetIds = Boolean(detail.yes_token_id || detail.no_token_id);
  const assetKey = `${detail.yes_token_id ?? ""}|${detail.no_token_id ?? ""}`;
  const [connectionState, setConnectionState] = useState<"idle" | "connecting" | "live" | "reconnecting" | "offline">(
    hasAssetIds ? "connecting" : "offline",
  );
  const [liveTrades, setLiveTrades] = useState<ActivityTrade[]>([]);
  const [quotes, setQuotes] = useState<Record<string, LiveQuote>>({});

  const socketRef = useRef<WebSocket | null>(null);
  const heartbeatRef = useRef<number | null>(null);
  const reconnectRef = useRef<number | null>(null);

  useEffect(() => {
    const assetIds = [detail.yes_token_id, detail.no_token_id].filter((value): value is string => Boolean(value));
    if (assetIds.length === 0) {
      setConnectionState("offline");
      return undefined;
    }

    let cancelled = false;

    const clearTimers = () => {
      if (heartbeatRef.current !== null) {
        window.clearInterval(heartbeatRef.current);
        heartbeatRef.current = null;
      }
      if (reconnectRef.current !== null) {
        window.clearTimeout(reconnectRef.current);
        reconnectRef.current = null;
      }
    };

    const connect = () => {
      if (cancelled) {
        return;
      }

      setConnectionState((current) => (current === "live" ? "reconnecting" : "connecting"));
      const socket = new WebSocket(MARKET_WS_URL);
      socketRef.current = socket;

      socket.onopen = () => {
        socket.send(
          JSON.stringify({
            type: "market",
            assets_ids: assetIds,
            custom_feature_enabled: true,
          }),
        );
        heartbeatRef.current = window.setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({}));
          }
        }, HEARTBEAT_MS);
        setConnectionState("live");
      };

      socket.onmessage = (event) => {
        let payload: unknown;
        try {
          payload = JSON.parse(event.data);
        } catch {
          return;
        }

        const messages = Array.isArray(payload) ? payload : [payload];
        for (const message of messages) {
          if (!message || typeof message !== "object") {
            continue;
          }

          const typedMessage = message as Record<string, unknown>;
          if (typedMessage.event_type === "last_trade_price") {
            const assetId = typeof typedMessage.asset_id === "string" ? typedMessage.asset_id : null;
            const tradeTs = normalizeTimestamp(typeof typedMessage.timestamp === "string" ? typedMessage.timestamp : null);
            const price = parseNumeric(typedMessage.price as string | number | null | undefined);
            const size = parseNumeric(typedMessage.size as string | number | null | undefined);
            const trade: ActivityTrade = {
              id: `${typedMessage.transaction_hash ?? tradeTs}-${assetId ?? "unknown"}`,
              tradeTs,
              assetId,
              outcome:
                assetId === detail.yes_token_id ? "Yes" : assetId === detail.no_token_id ? "No" : null,
              side: typeof typedMessage.side === "string" ? typedMessage.side.toUpperCase() : null,
              price,
              size,
              notional: price !== null && size !== null ? price * size : null,
              txHash: typeof typedMessage.transaction_hash === "string" ? typedMessage.transaction_hash : null,
              walletAddress: null,
              source: "live",
            };

            setLiveTrades((current) => {
              const next = [trade, ...current.filter((item) => item.id !== trade.id)];
              next.sort((left, right) => timestampToMillis(right.tradeTs) - timestampToMillis(left.tradeTs));
              return next.slice(0, 24);
            });
          }

          if (typedMessage.event_type === "best_bid_ask") {
            const assetId = typeof typedMessage.asset_id === "string" ? typedMessage.asset_id : null;
            if (!assetId) {
              continue;
            }
            setQuotes((current) => ({
              ...current,
              [assetId]: {
                bestBid: parseNumeric(typedMessage.best_bid as string | number | null | undefined),
                bestAsk: parseNumeric(typedMessage.best_ask as string | number | null | undefined),
                spread: parseNumeric(typedMessage.spread as string | number | null | undefined),
                timestamp: normalizeTimestamp(typeof typedMessage.timestamp === "string" ? typedMessage.timestamp : null),
              },
            }));
          }
        }
      };

      socket.onerror = () => {
        setConnectionState("reconnecting");
      };

      socket.onclose = () => {
        clearTimers();
        if (cancelled) {
          return;
        }
        setConnectionState("reconnecting");
        reconnectRef.current = window.setTimeout(connect, RECONNECT_MS);
      };
    };

    connect();

    return () => {
      cancelled = true;
      clearTimers();
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [assetKey, detail.no_token_id, detail.yes_token_id]);

  const seededTrades = buildSeedTrades(detail, trades);
  const tradeMap = new Map<string, ActivityTrade>();
  for (const trade of [...liveTrades, ...seededTrades]) {
    if (!tradeMap.has(trade.id)) {
      tradeMap.set(trade.id, trade);
    }
  }
  const recentTrades = Array.from(tradeMap.values()).sort(
    (left, right) => timestampToMillis(right.tradeTs) - timestampToMillis(left.tradeTs),
  );

  const latestTrade = recentTrades[0] ?? null;
  const largestBuy =
    recentTrades
      .filter((trade) => trade.side === "BUY" && trade.notional !== null)
      .sort((left, right) => (right.notional ?? 0) - (left.notional ?? 0))[0] ?? null;
  const largestTrade =
    recentTrades
      .filter((trade) => trade.notional !== null)
      .sort((left, right) => (right.notional ?? 0) - (left.notional ?? 0))[0] ?? null;

  const biggestHolder =
    [...holders]
      .filter((holder) => holder.amount !== null)
      .sort((left, right) => (right.amount ?? 0) - (left.amount ?? 0))[0] ?? null;
  const biggestYesHolder =
    [...holders]
      .filter((holder) => holder.amount !== null && holder.outcome_index === 0)
      .sort((left, right) => (right.amount ?? 0) - (left.amount ?? 0))[0] ?? null;
  const biggestNoHolder =
    [...holders]
      .filter((holder) => holder.amount !== null && holder.outcome_index === 1)
      .sort((left, right) => (right.amount ?? 0) - (left.amount ?? 0))[0] ?? null;

  const yesQuote = detail.yes_token_id ? quotes[detail.yes_token_id] : undefined;
  const noQuote = detail.no_token_id ? quotes[detail.no_token_id] : undefined;

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Live Activity</CardTitle>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Real-time market-channel updates layered over the persisted trade history for this market.
          </p>
        </div>
        <Badge
          className={
            connectionState === "live"
              ? "border-good/30 bg-good/10 text-good"
              : connectionState === "offline"
                ? "border-slate-300 bg-slate-100 text-slate-700"
                : "border-warn/30 bg-warn/10 text-warn"
          }
        >
          {connectionState}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-2xl border border-line px-4 py-3">
            <div className="text-xs uppercase tracking-[0.14em] text-muted">Latest trade</div>
            <div className="mt-2 font-mono text-lg">{fmtNumber(latestTrade?.price ?? null, 3)}</div>
            <p className="mt-1 text-sm text-slate-600">
              {latestTrade?.outcome ?? "n/a"} {latestTrade?.side?.toLowerCase() ?? ""}
            </p>
          </div>
          <div className="rounded-2xl border border-line px-4 py-3">
            <div className="text-xs uppercase tracking-[0.14em] text-muted">Largest buy</div>
            <div className="mt-2 font-mono text-lg">{fmtNumber(largestBuy?.notional ?? null, 2)}</div>
            <p className="mt-1 text-sm text-slate-600">{largestBuy?.outcome ?? "n/a"}</p>
          </div>
          <div className="rounded-2xl border border-line px-4 py-3">
            <div className="text-xs uppercase tracking-[0.14em] text-muted">Biggest holder</div>
            <div className="mt-2 font-mono text-lg">{fmtNumber(biggestHolder?.amount ?? null, 2)}</div>
            <p className="mt-1 text-sm text-slate-600">
              {biggestHolder?.outcome_index === 0 ? "Yes" : biggestHolder?.outcome_index === 1 ? "No" : "n/a"} side
            </p>
          </div>
          <div className="rounded-2xl border border-line px-4 py-3">
            <div className="text-xs uppercase tracking-[0.14em] text-muted">Largest trade</div>
            <div className="mt-2 font-mono text-lg">{fmtNumber(largestTrade?.notional ?? null, 2)}</div>
            <p className="mt-1 text-sm text-slate-600">{largestTrade?.side?.toLowerCase() ?? "n/a"}</p>
          </div>
        </div>

        <div className="grid gap-3 lg:grid-cols-2">
          <div className="rounded-2xl border border-line px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-[0.14em] text-muted">Yes live quote</div>
                <div className="mt-2 font-mono text-lg">
                  {fmtNumber(yesQuote?.bestBid ?? null, 3)} / {fmtNumber(yesQuote?.bestAsk ?? null, 3)}
                </div>
              </div>
              <Badge className="border-accent/30 bg-accent/10 text-accent">Spread {fmtNumber(yesQuote?.spread ?? null, 3)}</Badge>
            </div>
            <p className="mt-2 text-xs text-muted">Updated {fmtDateTime(yesQuote?.timestamp ?? null)}</p>
          </div>
          <div className="rounded-2xl border border-line px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-[0.14em] text-muted">No live quote</div>
                <div className="mt-2 font-mono text-lg">
                  {fmtNumber(noQuote?.bestBid ?? null, 3)} / {fmtNumber(noQuote?.bestAsk ?? null, 3)}
                </div>
              </div>
              <Badge className="border-accent/30 bg-accent/10 text-accent">Spread {fmtNumber(noQuote?.spread ?? null, 3)}</Badge>
            </div>
            <p className="mt-2 text-xs text-muted">Updated {fmtDateTime(noQuote?.timestamp ?? null)}</p>
          </div>
        </div>

        <div className="grid gap-3 lg:grid-cols-3">
          <div className="rounded-2xl border border-line px-4 py-3">
            <div className="text-xs uppercase tracking-[0.14em] text-muted">Top yes holder</div>
            <div className="mt-2 font-mono text-lg">{fmtNumber(biggestYesHolder?.amount ?? null, 2)}</div>
            <div className="mt-2 text-sm text-slate-600">
              <PolygonscanLink kind="address" value={biggestYesHolder?.wallet_address} />
            </div>
          </div>
          <div className="rounded-2xl border border-line px-4 py-3">
            <div className="text-xs uppercase tracking-[0.14em] text-muted">Top no holder</div>
            <div className="mt-2 font-mono text-lg">{fmtNumber(biggestNoHolder?.amount ?? null, 2)}</div>
            <div className="mt-2 text-sm text-slate-600">
              <PolygonscanLink kind="address" value={biggestNoHolder?.wallet_address} />
            </div>
          </div>
          <div className="rounded-2xl border border-line px-4 py-3">
            <div className="text-xs uppercase tracking-[0.14em] text-muted">Market page</div>
            <div className="mt-2 text-sm text-slate-600">
              {detail.market_url ? (
                <a href={detail.market_url} target="_blank" rel="noreferrer" className="font-medium text-accent hover:text-slate-950">
                  Open on Polymarket
                </a>
              ) : (
                "n/a"
              )}
            </div>
          </div>
        </div>

        {recentTrades.length === 0 ? (
          <div className="rounded-2xl border border-line bg-slate-50 px-4 py-6 text-sm text-slate-600">
            No trade activity is available for this market yet.
          </div>
        ) : (
          <div className="space-y-3">
            {recentTrades.slice(0, 10).map((trade) => (
              <div key={trade.id} className="rounded-2xl border border-line px-4 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="font-medium uppercase">
                        {trade.side?.toLowerCase() ?? "trade"} {trade.outcome ?? ""}
                      </div>
                      <Badge className={trade.source === "live" ? "border-good/30 bg-good/10 text-good" : ""}>
                        {trade.source === "live" ? "Live" : "History"}
                      </Badge>
                    </div>
                    <div className="mt-1 font-mono text-xs text-muted">{fmtDateTime(trade.tradeTs)}</div>
                    <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-600">
                      <span>
                        Tx: <PolygonscanLink kind="tx" value={trade.txHash} />
                      </span>
                      <span>
                        Wallet: <PolygonscanLink kind="address" value={trade.walletAddress} />
                      </span>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono">{fmtNumber(trade.notional, 2)}</div>
                    <div className="font-mono text-xs text-muted">
                      {fmtNumber(trade.price, 3)} x {fmtNumber(trade.size, 2)}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
