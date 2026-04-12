import {
  mockAlerts,
  mockBacktests,
  mockHolders,
  mockJobActionResponse,
  mockLatentBacktests,
  mockMarketDetail,
  mockMarketTradeAftermath,
  mockMarkets,
  mockOverview,
  mockSystem,
  mockTimeSeries,
  mockTrades,
  mockWatchlist,
} from "@/lib/mock-data";

function stripTrailingSlash(value: string) {
  return value.endsWith("/") ? value.slice(0, -1) : value;
}

const INTERNAL_API_BASE_URL = stripTrailingSlash(
  process.env.SCANNER_API_INTERNAL_URL ?? process.env.SCANNER_API_BASE_URL ?? "http://127.0.0.1:8000",
);
const PUBLIC_API_BASE_URL = stripTrailingSlash(process.env.NEXT_PUBLIC_SCANNER_API_BASE_URL ?? "/scanner-api");
const API_MODE = process.env.NEXT_PUBLIC_SCANNER_API_MODE ?? process.env.SCANNER_API_MODE ?? "live";

function getApiBaseUrl() {
  return typeof window === "undefined" ? INTERNAL_API_BASE_URL : PUBLIC_API_BASE_URL;
}

export type Overview = typeof mockOverview;
export type MarketsResponse = typeof mockMarkets;
export type WatchlistResponse = typeof mockWatchlist;
export type AlertsResponse = typeof mockAlerts;
export type MarketDetail = typeof mockMarketDetail;
export type TimeSeriesResponse = typeof mockTimeSeries;
export type HoldersResponse = typeof mockHolders;
export type TradesResponse = typeof mockTrades;
export type MarketTradeAftermathResponse = typeof mockMarketTradeAftermath;
export type BacktestsResponse = typeof mockBacktests;
export type LatentBacktestsResponse = typeof mockLatentBacktests;
export type SystemResponse = typeof mockSystem;
export type JobActionResponse = typeof mockJobActionResponse;

type MockKey =
  | "overview"
  | "markets"
  | "watchlist"
  | "alerts"
  | "marketDetail"
  | "timeseries"
  | "holders"
  | "trades"
  | "tradeAftermath"
  | "backtests"
  | "latentBacktests"
  | "jobAction"
  | "system";

const mockMap: Record<MockKey, unknown> = {
  overview: mockOverview,
  markets: mockMarkets,
  watchlist: mockWatchlist,
  alerts: mockAlerts,
  marketDetail: mockMarketDetail,
  timeseries: mockTimeSeries,
  holders: mockHolders,
  trades: mockTrades,
  tradeAftermath: mockMarketTradeAftermath,
  backtests: mockBacktests,
  latentBacktests: mockLatentBacktests,
  jobAction: mockJobActionResponse,
  system: mockSystem,
};

async function fetchJson<T>(path: string, mockKey: MockKey): Promise<T> {
  if (API_MODE === "mock") {
    return structuredClone(mockMap[mockKey]) as T;
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  }

  return (await response.json()) as T;
}

async function postJson<T>(path: string, body: unknown, mockKey: MockKey): Promise<T> {
  if (API_MODE === "mock") {
    return structuredClone(mockMap[mockKey]) as T;
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    method: "POST",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  }

  return (await response.json()) as T;
}

export function getOverview() {
  return fetchJson<Overview>("/api/v1/overview", "overview");
}

export function getMarkets(params?: {
  search?: string;
  status?: string;
  history?: string;
  watchlistOnly?: boolean;
  sort?: string;
}) {
  const query = new URLSearchParams();
  if (params?.search) query.set("search", params.search);
  if (params?.status) query.set("status", params.status);
  if (params?.history) query.set("history", params.history);
  if (params?.watchlistOnly) query.set("watchlist_only", "true");
  if (params?.sort) query.set("sort", params.sort);
  const queryString = query.toString();
  const suffix = queryString ? `?${queryString}` : "";
  return fetchJson<MarketsResponse>(`/api/v1/markets${suffix}`, "markets");
}

export function getWatchlist(warmupOnly?: boolean) {
  const suffix = warmupOnly === undefined ? "" : `?warmup_only=${String(warmupOnly)}`;
  return fetchJson<WatchlistResponse>(`/api/v1/watchlist${suffix}`, "watchlist");
}

export function getAlerts() {
  return fetchJson<AlertsResponse>("/api/v1/alerts", "alerts");
}

export function getMarketDetail(conditionId: string) {
  if (API_MODE === "mock" && conditionId !== mockMarketDetail.condition_id) {
    return Promise.resolve(structuredClone({ ...mockMarketDetail, condition_id: conditionId }) as MarketDetail);
  }
  return fetchJson<MarketDetail>(`/api/v1/markets/${conditionId}`, "marketDetail");
}

export function getMarketTimeseries(conditionId: string) {
  if (API_MODE === "mock" && conditionId !== mockTimeSeries.condition_id) {
    return Promise.resolve(structuredClone({ ...mockTimeSeries, condition_id: conditionId }) as TimeSeriesResponse);
  }
  return fetchJson<TimeSeriesResponse>(`/api/v1/markets/${conditionId}/timeseries?hours=168`, "timeseries");
}

export function getMarketHolders(conditionId: string) {
  if (API_MODE === "mock" && conditionId !== mockHolders.condition_id) {
    return Promise.resolve(structuredClone({ ...mockHolders, condition_id: conditionId }) as HoldersResponse);
  }
  return fetchJson<HoldersResponse>(`/api/v1/markets/${conditionId}/holders`, "holders");
}

export function getMarketTrades(conditionId: string) {
  if (API_MODE === "mock" && conditionId !== mockTrades.condition_id) {
    return Promise.resolve(structuredClone({ ...mockTrades, condition_id: conditionId }) as TradesResponse);
  }
  return fetchJson<TradesResponse>(`/api/v1/markets/${conditionId}/trades`, "trades");
}

export function getMarketTradeAftermath(conditionId: string) {
  if (API_MODE === "mock" && conditionId !== mockMarketTradeAftermath.condition_id) {
    return Promise.resolve(structuredClone({ ...mockMarketTradeAftermath, condition_id: conditionId }) as MarketTradeAftermathResponse);
  }
  return fetchJson<MarketTradeAftermathResponse>(
    `/api/v1/markets/${conditionId}/trade-aftermath?limit=8&min_notional=1000&side=buy&outcome=all`,
    "tradeAftermath",
  );
}

export function getBacktests() {
  return fetchJson<BacktestsResponse>("/api/v1/research/backtests", "backtests");
}

export function getLatentBacktests() {
  return fetchJson<LatentBacktestsResponse>("/api/v1/research/latent-backtests", "latentBacktests");
}

export function runSystemAction(body: {
  action: string;
  hours?: number[];
  confirm_hours?: number;
  max_drift?: number;
  min_notional?: number;
  min_wallet_score?: number;
}) {
  return postJson<JobActionResponse>("/api/v1/system/actions/run", body, "jobAction");
}

export function getSystem() {
  return fetchJson<SystemResponse>("/api/v1/system", "system");
}
