type MarketItem = {
  condition_id: string;
  title: string;
  market_id: string | null;
  event_slug: string;
  market_slug: string;
  market_url: string;
  category: string;
  active: boolean;
  closed: boolean;
  accepting_orders: boolean | null;
  end_date: string | null;
  latest_snapshot_ts: string;
  current_yes_price: number;
  yes_top5_seen_share: number;
  observed_holder_wallets: number;
  history_ready_6h: boolean;
  history_ready_24h: boolean;
  history_ready_72h: boolean;
  watchlist_flag: boolean;
  warmup_only: boolean;
  trade_enriched: boolean;
  latest_alert_ts: string | null;
  latest_alert_severity: string | null;
};

type WatchlistItem = {
  snapshot_ts: string;
  condition_id: string;
  market_title: string;
  market_url: string;
  current_yes_price: number;
  price_delta_6h: number | null;
  yes_top5_seen_share: number;
  price_anomaly_hit: boolean;
  holder_concentration_hit: boolean;
  wallet_quality_hit: boolean;
  warmup_only: boolean;
  history_ready_6h: boolean;
  trade_enriched: boolean;
  reason_summary: string;
  component_flags: Record<string, boolean>;
};

type AlertItem = {
  id: number;
  alert_ts: string;
  condition_id: string;
  market_title: string;
  market_url: string;
  alert_type: string;
  score: number;
  score_total: number;
  score_price_anomaly: number;
  score_holder_concentration: number;
  score_wallet_quality: number;
  score_trade_flow: number;
  current_yes_price: number;
  price_delta_6h: number | null;
  price_delta_24h: number | null;
  price_delta_72h: number | null;
  severity: string;
  confidence: string;
  action_label: string;
  reason_summary: string;
  summary: string;
  reasons: string[];
  sent: boolean;
};

type RecommendationItem = {
  condition_id: string;
  market_title: string;
  market_url: string;
  source: string;
  side: string;
  recommendation: string;
  status: string;
  conviction_score: number;
  severity: string | null;
  confidence: string | null;
  reason_summary: string;
  entry_ts: string;
  entry_price: number;
  entry_yes_price: number;
  latest_snapshot_ts: string | null;
  current_price: number;
  current_yes_price: number;
  current_return: number | null;
  final_price: number | null;
  final_yes_price: number | null;
  outcome_return: number | null;
  outcome_verdict: string | null;
  closed: boolean;
  closed_time: string | null;
  history_ready_6h: boolean;
  warmup_only: boolean;
  trade_enriched: boolean;
};

type AggregateBucket = {
  key: string;
  count: number;
  avg_return: number | null;
  positive_rate: number | null;
};

type TradeAftermathPoint = {
  snapshot_ts: string;
  yes_price: number | null;
  no_price: number | null;
  yes_top5_seen_share: number | null;
  no_top5_seen_share: number | null;
  observed_holder_wallets: number | null;
  relative_hours: number | null;
};

type TradeAftermathHorizon = {
  target_hours: number;
  snapshot_ts: string | null;
  observed_hours_after_trade: number | null;
  yes_price: number | null;
  no_price: number | null;
  yes_return: number | null;
  no_return: number | null;
  outcome_price: number | null;
  outcome_return: number | null;
};

type TradeAftermathItem = {
  trade_key: string;
  trade_ts: string;
  wallet_address: string | null;
  side: string | null;
  outcome: string | null;
  price: number | null;
  size: number | null;
  notional: number | null;
  tx_hash: string | null;
  title: string | null;
  politics_score: number | null;
  overall_score: number | null;
  politics_pnl_rank: number | null;
  overall_pnl_rank: number | null;
  entry_snapshot_ts: string | null;
  entry_snapshot_lag_minutes: number | null;
  entry_yes_price: number | null;
  entry_no_price: number | null;
  current_snapshot_ts: string | null;
  current_yes_price: number | null;
  current_no_price: number | null;
  current_yes_return: number | null;
  current_no_return: number | null;
  current_outcome_price: number | null;
  current_outcome_return: number | null;
  horizons: TradeAftermathHorizon[];
  surrounding_points: TradeAftermathPoint[];
};

export const mockOverview = {
  generated_at: "2026-04-09 13:50:00",
  db_age: "0d 2h 48m",
  first_snapshot_ts: "2026-04-09 11:01:45",
  latest_snapshot_ts: "2026-04-09 13:43:08",
  markets_discovered: 1610,
  active_scanner_scope: 250,
  markets_with_enough_6h_history: 0,
  markets_with_enough_24h_history: 0,
  markets_with_enough_72h_history: 0,
  watchlist_candidates: 64,
  alerts_count: 0,
  backtestable_alerts_6h: 0,
  backtestable_alerts_24h: 0,
  backtestable_alerts_72h: 0,
  latest_watchlist_snapshot_ts: "2026-04-09 13:43:08",
  latest_backtest_ts: "2026-04-09 13:50:00",
};

export const mockMarkets: { total: number; items: MarketItem[] } = {
  total: 2,
  items: [
    {
      condition_id: "0x7335fb4a2d4a63565d1cc79a0b3ed4d8170ed6c4c2465c46fd59892e20a31a01",
      title: "Valorant: Dragon Ranger Gaming vs Wolves Esports (BO3)",
      market_id: "1467001",
      event_slug: "val-drg-wol-2026-04-09",
      market_slug: "val-drg-wol-2026-04-09",
      market_url: "https://polymarket.com/event/val-drg-wol-2026-04-09",
      category: "Sports",
      active: true,
      closed: false,
      accepting_orders: true,
      end_date: "2026-04-10T18:00:00Z",
      latest_snapshot_ts: "2026-04-09 13:43:08",
      current_yes_price: 0.83,
      yes_top5_seen_share: 0.6582,
      observed_holder_wallets: 40,
      history_ready_6h: false,
      history_ready_24h: false,
      history_ready_72h: false,
      watchlist_flag: true,
      warmup_only: true,
      trade_enriched: true,
      latest_alert_ts: null,
      latest_alert_severity: null,
    },
    {
      condition_id: "0x8393100160719b069c45925bf183143c523c377a72a35874560b5ede596ef648",
      title: "Valorant: Dragon Ranger Gaming vs Wolves Esports - Map 2 Winner",
      market_id: "1467002",
      event_slug: "val-drg-wol-2026-04-09",
      market_slug: "val-drg-wol-2026-04-09-game2",
      market_url: "https://polymarket.com/event/val-drg-wol-2026-04-09",
      category: "Sports",
      active: true,
      closed: false,
      accepting_orders: false,
      end_date: "2026-04-10T17:10:00Z",
      latest_snapshot_ts: "2026-04-09 13:43:08",
      current_yes_price: 0.12,
      yes_top5_seen_share: 0.7191,
      observed_holder_wallets: 35,
      history_ready_6h: false,
      history_ready_24h: false,
      history_ready_72h: false,
      watchlist_flag: false,
      warmup_only: false,
      trade_enriched: false,
      latest_alert_ts: null,
      latest_alert_severity: null,
    },
  ],
};

export const mockWatchlist: { snapshot_ts: string; total: number; items: WatchlistItem[] } = {
  snapshot_ts: "2026-04-09 13:43:08",
  total: 2,
  items: [
    {
      snapshot_ts: "2026-04-09 13:43:08",
      condition_id: mockMarkets.items[0].condition_id,
      market_title: mockMarkets.items[0].title,
      market_url: mockMarkets.items[0].market_url,
      current_yes_price: 0.83,
      price_delta_6h: null,
      yes_top5_seen_share: 0.6582,
      price_anomaly_hit: false,
      holder_concentration_hit: true,
      wallet_quality_hit: true,
      warmup_only: true,
      history_ready_6h: false,
      trade_enriched: true,
      reason_summary: "holder concentration, wallet quality (warm-up)",
      component_flags: {
        price_anomaly: false,
        holder_concentration: true,
        wallet_quality: true,
        history_ready_6h: false,
      },
    },
    {
      snapshot_ts: "2026-04-09 13:43:08",
      condition_id: mockMarkets.items[1].condition_id,
      market_title: mockMarkets.items[1].title,
      market_url: mockMarkets.items[1].market_url,
      current_yes_price: 0.12,
      price_delta_6h: null,
      yes_top5_seen_share: 0.7191,
      price_anomaly_hit: true,
      holder_concentration_hit: false,
      wallet_quality_hit: false,
      warmup_only: true,
      history_ready_6h: false,
      trade_enriched: false,
      reason_summary: "price anomaly (warm-up)",
      component_flags: {
        price_anomaly: true,
        holder_concentration: false,
        wallet_quality: false,
        history_ready_6h: false,
      },
    },
  ],
};

export const mockAlerts: { total: number; items: AlertItem[] } = {
  total: 0,
  items: [],
};

export const mockRecommendations: {
  total: number;
  actionable: number;
  monitoring: number;
  settled: number;
  items: RecommendationItem[];
} = {
  total: 3,
  actionable: 1,
  monitoring: 1,
  settled: 1,
  items: [
    {
      condition_id: mockMarkets.items[0].condition_id,
      market_title: mockMarkets.items[0].title,
      market_url: mockMarkets.items[0].market_url,
      source: "alert",
      side: "Yes",
      recommendation: "consider_yes",
      status: "actionable",
      conviction_score: 8.7,
      severity: "high",
      confidence: "medium",
      reason_summary: "Strong wallets accumulated into a price break while recent flow stayed net-buy.",
      entry_ts: "2026-04-09 13:43:08",
      entry_price: 0.71,
      entry_yes_price: 0.71,
      latest_snapshot_ts: "2026-04-10 01:10:00",
      current_price: 0.83,
      current_yes_price: 0.83,
      current_return: 0.169,
      final_price: null,
      final_yes_price: null,
      outcome_return: null,
      outcome_verdict: null,
      closed: false,
      closed_time: null,
      history_ready_6h: true,
      warmup_only: false,
      trade_enriched: true,
    },
    {
      condition_id: mockMarkets.items[1].condition_id,
      market_title: mockMarkets.items[1].title,
      market_url: mockMarkets.items[1].market_url,
      source: "watchlist",
      side: "Yes",
      recommendation: "wait_for_history",
      status: "monitoring",
      conviction_score: 1.5,
      severity: null,
      confidence: null,
      reason_summary: "Price anomaly is interesting, but the market is still in warm-up and does not have enough history.",
      entry_ts: "2026-04-09 13:43:08",
      entry_price: 0.12,
      entry_yes_price: 0.12,
      latest_snapshot_ts: "2026-04-09 13:43:08",
      current_price: 0.12,
      current_yes_price: 0.12,
      current_return: 0,
      final_price: null,
      final_yes_price: null,
      outcome_return: null,
      outcome_verdict: null,
      closed: false,
      closed_time: null,
      history_ready_6h: false,
      warmup_only: true,
      trade_enriched: false,
    },
    {
      condition_id: "0xclosedfixture",
      market_title: "Will candidate X win the nomination?",
      market_url: "https://polymarket.com/event/mock-closed-market",
      source: "alert",
      side: "Yes",
      recommendation: "consider_yes",
      status: "settled",
      conviction_score: 9.1,
      severity: "high",
      confidence: "high",
      reason_summary: "Wallet quality and trade flow both aligned before resolution.",
      entry_ts: "2026-04-05 09:15:00",
      entry_price: 0.63,
      entry_yes_price: 0.63,
      latest_snapshot_ts: "2026-04-07 18:00:00",
      current_price: 1,
      current_yes_price: 1,
      current_return: 0.5873,
      final_price: 1,
      final_yes_price: 1,
      outcome_return: 0.5873,
      outcome_verdict: "good_call",
      closed: true,
      closed_time: "2026-04-07 18:00:00",
      history_ready_6h: true,
      warmup_only: false,
      trade_enriched: true,
    },
  ],
};

export const mockMarketDetail = {
  condition_id: mockMarkets.items[0].condition_id,
  title: mockMarkets.items[0].title,
  description: "Scanner-scope market detail for mock mode.",
  category: "Sports",
  market_id: mockMarkets.items[0].market_id,
  question_id: "0xquestion",
  event_slug: mockMarkets.items[0].event_slug,
  market_slug: mockMarkets.items[0].market_slug,
  market_url: mockMarkets.items[0].market_url,
  active: true,
  closed: false,
  archived: false,
  accepting_orders: true,
  end_date: "2026-04-10 18:00:00",
  closed_time: null,
  yes_token_id: "yes-token",
  no_token_id: "no-token",
  image_url: "https://polymarket-upload.s3.us-east-2.amazonaws.com/mock-market.png",
  reward_asset_address: "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
  discovered_at: "2026-04-09 13:43:07",
  last_seen_at: "2026-04-09 13:43:07",
  current_yes_price: 0.83,
  current_no_price: 0.17,
  yes_top5_seen_share: 0.6582,
  no_top5_seen_share: 0.4421,
  observed_holder_wallets: 40,
  history_ready_6h: false,
  history_ready_24h: false,
  history_ready_72h: false,
  watchlist_flag: true,
  warmup_only: true,
  trade_enriched: true,
  recent_alert_count: 0,
  latest_alert_ts: null,
  latest_alert_severity: null,
  latest_watchlist_reason_summary: "holder concentration, wallet quality (warm-up)",
};

export const mockTimeSeries = {
  condition_id: mockMarketDetail.condition_id,
  hours: 168,
  items: [
    { snapshot_ts: "2026-04-09 11:01:45", yes_price: 0.78, no_price: 0.22, yes_top5_seen_share: 0.61, no_top5_seen_share: 0.39, observed_holder_wallets: 32 },
    { snapshot_ts: "2026-04-09 12:15:00", yes_price: 0.8, no_price: 0.2, yes_top5_seen_share: 0.63, no_top5_seen_share: 0.4, observed_holder_wallets: 35 },
    { snapshot_ts: "2026-04-09 13:43:08", yes_price: 0.83, no_price: 0.17, yes_top5_seen_share: 0.6582, no_top5_seen_share: 0.4421, observed_holder_wallets: 40 }
  ],
};

export const mockHolders = {
  condition_id: mockMarketDetail.condition_id,
  snapshot_ts: "2026-04-09 13:43:08",
  items: [
    { snapshot_ts: "2026-04-09 13:43:08", token_id: "yes-token", wallet_address: "0x1234567890abcdef1234567890abcdef12345678", amount: 1200, outcome_index: 0, rank: 1, politics_score: 78, overall_score: 62, politics_pnl_rank: 14, overall_pnl_rank: 28 },
    { snapshot_ts: "2026-04-09 13:43:08", token_id: "no-token", wallet_address: "0xabcdef1234567890abcdef1234567890abcdef12", amount: 870, outcome_index: 1, rank: 2, politics_score: null, overall_score: 33, politics_pnl_rank: null, overall_pnl_rank: 59 }
  ],
};

export const mockTrades = {
  condition_id: mockMarketDetail.condition_id,
  total: 2,
  items: [
    { trade_key: "trade-1", trade_ts: "2026-04-09 13:35:00", wallet_address: mockHolders.items[0].wallet_address, side: "buy", outcome: "Yes", price: 0.82, size: 120, notional: 98.4, tx_hash: "0xtx1", title: mockMarketDetail.title },
    { trade_key: "trade-2", trade_ts: "2026-04-09 13:31:00", wallet_address: mockHolders.items[1].wallet_address, side: "buy", outcome: "Yes", price: 0.81, size: 80, notional: 64.8, tx_hash: "0xtx2", title: mockMarketDetail.title }
  ],
};

export const mockMarketTradeAftermath: {
  condition_id: string;
  total: number;
  side: string | null;
  outcome: string | null;
  min_notional: number | null;
  items: TradeAftermathItem[];
} = {
  condition_id: mockMarketDetail.condition_id,
  total: 1,
  side: "buy",
  outcome: null,
  min_notional: 1000,
  items: [
    {
      trade_key: "trade-aftermath-1",
      trade_ts: "2026-04-09 13:35:00",
      wallet_address: "0x1234567890abcdef1234567890abcdef12345678",
      side: "buy",
      outcome: "Yes",
      price: 0.41,
      size: 3500,
      notional: 1435,
      tx_hash: "0xafter1",
      title: mockMarketDetail.title,
      politics_score: 78,
      overall_score: 62,
      politics_pnl_rank: 14,
      overall_pnl_rank: 28,
      entry_snapshot_ts: "2026-04-09 12:15:00",
      entry_snapshot_lag_minutes: 80,
      entry_yes_price: 0.4,
      entry_no_price: 0.6,
      current_snapshot_ts: "2026-04-10 13:43:08",
      current_yes_price: 0.83,
      current_no_price: 0.17,
      current_yes_return: 1.075,
      current_no_return: -0.7167,
      current_outcome_price: 0.83,
      current_outcome_return: 1.0244,
      horizons: [
        { target_hours: 6, snapshot_ts: "2026-04-09 19:40:00", observed_hours_after_trade: 6.08, yes_price: 0.48, no_price: 0.52, yes_return: 0.2, no_return: -0.1333, outcome_price: 0.48, outcome_return: 0.1707 },
        { target_hours: 24, snapshot_ts: "2026-04-10 13:43:08", observed_hours_after_trade: 24.13, yes_price: 0.83, no_price: 0.17, yes_return: 1.075, no_return: -0.7167, outcome_price: 0.83, outcome_return: 1.0244 },
        { target_hours: 72, snapshot_ts: null, observed_hours_after_trade: null, yes_price: null, no_price: null, yes_return: null, no_return: null, outcome_price: null, outcome_return: null },
      ],
      surrounding_points: [
        { snapshot_ts: "2026-04-09 11:01:45", yes_price: 0.38, no_price: 0.62, yes_top5_seen_share: 0.59, no_top5_seen_share: 0.41, observed_holder_wallets: 28, relative_hours: -2.55 },
        { snapshot_ts: "2026-04-09 12:15:00", yes_price: 0.4, no_price: 0.6, yes_top5_seen_share: 0.61, no_top5_seen_share: 0.39, observed_holder_wallets: 32, relative_hours: -1.33 },
        { snapshot_ts: "2026-04-09 19:40:00", yes_price: 0.48, no_price: 0.52, yes_top5_seen_share: 0.63, no_top5_seen_share: 0.37, observed_holder_wallets: 35, relative_hours: 6.08 },
        { snapshot_ts: "2026-04-10 06:00:00", yes_price: 0.68, no_price: 0.32, yes_top5_seen_share: 0.65, no_top5_seen_share: 0.35, observed_holder_wallets: 38, relative_hours: 16.42 },
        { snapshot_ts: "2026-04-10 13:43:08", yes_price: 0.83, no_price: 0.17, yes_top5_seen_share: 0.6582, no_top5_seen_share: 0.4421, observed_holder_wallets: 40, relative_hours: 24.13 },
      ],
    },
  ],
};

export const mockBacktests: {
  csv_path: string;
  exists: boolean;
  updated_at: string;
  total_rows: number;
  horizons: number[];
  score_buckets: AggregateBucket[];
  severity_buckets: AggregateBucket[];
  confidence_buckets: AggregateBucket[];
  alert_type_buckets: AggregateBucket[];
  missing_reason_buckets: AggregateBucket[];
  rows: Array<Record<string, string>>;
} = {
  csv_path: "data/backtest.csv",
  exists: true,
  updated_at: "2026-04-09 13:50:00",
  total_rows: 0,
  horizons: [6, 24, 72],
  score_buckets: [],
  severity_buckets: [],
  confidence_buckets: [],
  alert_type_buckets: [],
  missing_reason_buckets: [],
  rows: [],
};

export const mockLatentBacktests: {
  csv_path: string;
  exists: boolean;
  updated_at: string;
  total_rows: number;
  horizons: number[];
  score_buckets: AggregateBucket[];
  severity_buckets: AggregateBucket[];
  confidence_buckets: AggregateBucket[];
  alert_type_buckets: AggregateBucket[];
  missing_reason_buckets: AggregateBucket[];
  rows: Array<Record<string, string>>;
} = {
  csv_path: "data/latent_backtest.csv",
  exists: true,
  updated_at: "2026-04-10 09:05:00",
  total_rows: 3,
  horizons: [24, 72, 120],
  score_buckets: [
    { key: "24h|>=8.0", count: 3, avg_return: 0.142, positive_rate: 0.667 },
    { key: "72h|>=8.0", count: 3, avg_return: 0.221, positive_rate: 1.0 },
  ],
  severity_buckets: [
    { key: "24h|high", count: 2, avg_return: 0.181, positive_rate: 1.0 },
    { key: "24h|medium", count: 1, avg_return: 0.064, positive_rate: 0.0 },
  ],
  confidence_buckets: [],
  alert_type_buckets: [
    { key: "24h|latent_strong_wallet_entry", count: 3, avg_return: 0.142, positive_rate: 0.667 },
  ],
  missing_reason_buckets: [],
  rows: [],
};

export const mockJobActionResponse = {
  job_name: "latent-backtest",
  status: "completed",
  rows_written: 3,
  meta: { rows: 3 },
  output_path: "data/latent_backtest.csv",
};

export const mockSystem = {
  overview: mockOverview,
  backtest_csv_path: "data/backtest.csv",
  backtest_exists: true,
  backtest_updated_at: "2026-04-09 13:50:00",
  latent_backtest_csv_path: "data/latent_backtest.csv",
  latent_backtest_exists: true,
  latent_backtest_updated_at: "2026-04-10 09:05:00",
  recent_job_runs: [
    {
      id: 1,
      job_name: "snapshot",
      started_at: "2026-04-09 13:42:00",
      finished_at: "2026-04-09 13:43:08",
      status: "completed",
      rows_written: 64,
      meta: {
        markets: 250,
        holder_rows: 512,
        watchlist_candidates: 64,
        trade_enriched: 25,
      },
      error_text: null,
    },
  ],
};
