from __future__ import annotations

import psycopg
from psycopg.rows import dict_row
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from .models import Alert, MarketRecord
from .recommendations import recommendation_from_alert, recommendation_from_watchlist
from .utils import safe_json_dumps, utc_now_iso


class Database:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.conn = psycopg.connect(database_url, row_factory=dict_row)
        self.conn.autocommit = False

    def init_schema(self, schema_path: Path) -> None:
        sql = schema_path.read_text(encoding="utf-8")
        # Execute each statement individually (psycopg3 doesn't support executescript)
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        with self.conn.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
        self._migrate_schema()
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def _table_columns(self, table_name: str) -> set[str]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = %s AND table_schema = 'public'
                """,
                (table_name,),
            )
            return {row["column_name"] for row in cur.fetchall()}

    def _ensure_column(self, table_name: str, column_name: str, definition: str) -> None:
        columns = self._table_columns(table_name)
        if column_name in columns:
            return
        with self.conn.cursor() as cur:
            cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

    def _migrate_schema(self) -> None:
        market_columns = {
            "market_id": "TEXT",
            "question_id": "TEXT",
            "market_url": "TEXT",
            "accepting_orders": "INTEGER",
            "closed_time": "TEXT",
            "image_url": "TEXT",
            "reward_asset_address": "TEXT",
        }
        for column_name, definition in market_columns.items():
            self._ensure_column("markets", column_name, definition)

        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE markets
                SET
                    market_id = COALESCE(market_id, raw_json::json->>'id'),
                    question_id = COALESCE(question_id, raw_json::json->>'questionID'),
                    market_url = COALESCE(
                        market_url,
                        CASE
                            WHEN COALESCE(event_slug, slug) IS NOT NULL
                            THEN 'https://polymarket.com/event/' || COALESCE(event_slug, slug)
                        END
                    ),
                    accepting_orders = COALESCE(accepting_orders, (raw_json::json->>'acceptingOrders')::integer),
                    end_date = COALESCE(
                        end_date,
                        raw_json::json->>'endDate',
                        raw_json::json->>'umaEndDate',
                        raw_json::json->>'closedTime'
                    ),
                    closed_time = COALESCE(closed_time, raw_json::json->>'closedTime'),
                    image_url = COALESCE(
                        image_url,
                        raw_json::json->>'image',
                        raw_json::json->>'icon'
                    ),
                    reward_asset_address = COALESCE(
                        reward_asset_address,
                        raw_json::json->'clobRewards'->0->>'assetAddress'
                    )
                """
            )

        alert_columns = {
            "score_total": "REAL NOT NULL DEFAULT 0",
            "score_price_anomaly": "REAL NOT NULL DEFAULT 0",
            "score_holder_concentration": "REAL NOT NULL DEFAULT 0",
            "score_wallet_quality": "REAL NOT NULL DEFAULT 0",
            "score_trade_flow": "REAL NOT NULL DEFAULT 0",
            "market_title": "TEXT",
            "market_url": "TEXT",
            "yes_token_id": "TEXT",
            "current_yes_price": "REAL",
            "price_delta_6h": "REAL",
            "price_delta_24h": "REAL",
            "price_delta_72h": "REAL",
            "severity": "TEXT",
            "confidence": "TEXT",
            "action_label": "TEXT",
            "reason_summary": "TEXT",
        }
        for column_name, definition in alert_columns.items():
            self._ensure_column("alerts", column_name, definition)

        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE alerts
                SET
                    score_total = CASE
                        WHEN score_total = 0 AND score IS NOT NULL THEN score
                        ELSE score_total
                    END,
                    reason_summary = COALESCE(reason_summary, summary)
                """
            )

        recommendation_columns = {
            "entry_ts": "TEXT",
            "condition_id": "TEXT",
            "source": "TEXT",
            "market_title": "TEXT",
            "market_url": "TEXT",
            "side": "TEXT",
            "recommendation": "TEXT",
            "status": "TEXT",
            "conviction_score": "REAL NOT NULL DEFAULT 0",
            "severity": "TEXT",
            "confidence": "TEXT",
            "reason_summary": "TEXT",
            "entry_price": "REAL",
            "entry_yes_price": "REAL",
            "history_ready_6h": "INTEGER NOT NULL DEFAULT 0",
            "warmup_only": "INTEGER NOT NULL DEFAULT 0",
            "trade_enriched": "INTEGER NOT NULL DEFAULT 0",
            "source_meta_json": "TEXT",
            "created_at": "TEXT",
        }
        for column_name, definition in recommendation_columns.items():
            self._ensure_column("recommendations", column_name, definition)

        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE recommendations
                SET created_at = COALESCE(created_at, entry_ts, %s)
                """,
                (utc_now_iso(),),
            )
            cur.execute(
                """
                UPDATE recommendations
                SET entry_price = COALESCE(entry_price, entry_yes_price)
                """
            )

        watchlist_columns = {
            "side": "TEXT NOT NULL DEFAULT 'Yes'",
            "current_no_price": "REAL",
            "no_price_delta_6h": "REAL",
            "no_top5_seen_share": "REAL",
        }
        for column_name, definition in watchlist_columns.items():
            self._ensure_column("watchlist_candidates", column_name, definition)

        self._backfill_recommendations_if_empty()

    def upsert_event(self, event: Dict[str, Any]) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events (
                    event_id, slug, title, description, category, subcategory, active, closed, archived,
                    liquidity, volume, volume24hr, open_interest, end_date, updated_at, raw_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(event_id) DO UPDATE SET
                    slug=EXCLUDED.slug,
                    title=EXCLUDED.title,
                    description=EXCLUDED.description,
                    category=EXCLUDED.category,
                    subcategory=EXCLUDED.subcategory,
                    active=EXCLUDED.active,
                    closed=EXCLUDED.closed,
                    archived=EXCLUDED.archived,
                    liquidity=EXCLUDED.liquidity,
                    volume=EXCLUDED.volume,
                    volume24hr=EXCLUDED.volume24hr,
                    open_interest=EXCLUDED.open_interest,
                    end_date=EXCLUDED.end_date,
                    updated_at=EXCLUDED.updated_at,
                    raw_json=EXCLUDED.raw_json
                """,
                (
                    str(event.get("id")),
                    event.get("slug"),
                    event.get("title"),
                    event.get("description"),
                    event.get("category"),
                    event.get("subcategory"),
                    int(bool(event.get("active"))),
                    int(bool(event.get("closed"))),
                    int(bool(event.get("archived"))),
                    event.get("liquidity"),
                    event.get("volume"),
                    event.get("volume24hr"),
                    event.get("openInterest"),
                    event.get("endDate"),
                    utc_now_iso(),
                    safe_json_dumps(event),
                ),
            )

    def upsert_market(self, market: MarketRecord) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO markets (
                    condition_id, event_id, event_slug, slug, market_id, question_id, market_url, title, description, category,
                    active, closed, archived, accepting_orders, end_date, closed_time, yes_token_id, no_token_id, image_url,
                    reward_asset_address, discovered_at, last_seen_at, raw_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(condition_id) DO UPDATE SET
                    event_id=COALESCE(EXCLUDED.event_id, markets.event_id),
                    event_slug=COALESCE(EXCLUDED.event_slug, markets.event_slug),
                    slug=COALESCE(EXCLUDED.slug, markets.slug),
                    market_id=COALESCE(EXCLUDED.market_id, markets.market_id),
                    question_id=COALESCE(EXCLUDED.question_id, markets.question_id),
                    market_url=COALESCE(EXCLUDED.market_url, markets.market_url),
                    title=EXCLUDED.title,
                    description=COALESCE(EXCLUDED.description, markets.description),
                    category=COALESCE(EXCLUDED.category, markets.category),
                    active=EXCLUDED.active,
                    closed=EXCLUDED.closed,
                    archived=EXCLUDED.archived,
                    accepting_orders=COALESCE(EXCLUDED.accepting_orders, markets.accepting_orders),
                    end_date=COALESCE(EXCLUDED.end_date, markets.end_date),
                    closed_time=COALESCE(EXCLUDED.closed_time, markets.closed_time),
                    yes_token_id=COALESCE(EXCLUDED.yes_token_id, markets.yes_token_id),
                    no_token_id=COALESCE(EXCLUDED.no_token_id, markets.no_token_id),
                    image_url=COALESCE(EXCLUDED.image_url, markets.image_url),
                    reward_asset_address=COALESCE(EXCLUDED.reward_asset_address, markets.reward_asset_address),
                    last_seen_at=EXCLUDED.last_seen_at,
                    raw_json=EXCLUDED.raw_json
                """,
                (
                    market.condition_id,
                    market.event_id,
                    market.event_slug,
                    market.slug,
                    market.market_id,
                    market.question_id,
                    market.market_url,
                    market.title,
                    market.description,
                    market.category,
                    int(market.active),
                    int(market.closed),
                    int(market.archived),
                    int(market.accepting_orders) if market.accepting_orders is not None else None,
                    market.end_date,
                    market.closed_time,
                    market.yes_token_id,
                    market.no_token_id,
                    market.image_url,
                    market.reward_asset_address,
                    utc_now_iso(),
                    utc_now_iso(),
                    market.raw_json,
                ),
            )

    def commit(self) -> None:
        self.conn.commit()

    def rollback(self) -> None:
        self.conn.rollback()

    def get_active_markets(self, limit: int = 250) -> List[Dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM markets
                WHERE active = 1 AND closed = 0
                ORDER BY ctid DESC
                LIMIT %s
                """,
                (limit,),
            )
            return list(cur.fetchall())

    def get_unclosed_recommended_condition_ids(self, limit: int = 250) -> List[str]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT m.condition_id
                FROM markets m
                WHERE COALESCE(m.closed, 0) = 0
                  AND (
                    EXISTS (SELECT 1 FROM recommendations r WHERE r.condition_id = m.condition_id)
                    OR EXISTS (SELECT 1 FROM alerts a WHERE a.condition_id = m.condition_id)
                    OR EXISTS (SELECT 1 FROM watchlist_candidates wc WHERE wc.condition_id = m.condition_id)
                  )
                ORDER BY m.condition_id
                LIMIT %s
                """,
                (limit,),
            )
            return [row["condition_id"] for row in cur.fetchall()]

    def get_market_count(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM markets")
            row = cur.fetchone()
            return int(row["n"]) if row else 0

    def get_snapshot_bounds(self) -> Dict[str, Any] | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    MIN(snapshot_ts) AS first_snapshot_ts,
                    MAX(snapshot_ts) AS latest_snapshot_ts,
                    COUNT(*) AS snapshot_rows,
                    COUNT(DISTINCT condition_id) AS snapshot_markets
                FROM market_snapshots
                """
            )
            return cur.fetchone()

    def count_history_ready_markets(self, condition_ids: Sequence[str], hours: int) -> int:
        if not condition_ids:
            return 0
        placeholders = ",".join("%s" for _ in condition_ids)
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                WITH latest AS (
                    SELECT condition_id, MAX(snapshot_ts) AS latest_snapshot_ts
                    FROM market_snapshots
                    WHERE condition_id IN ({placeholders})
                    GROUP BY condition_id
                )
                SELECT COUNT(*) AS n
                FROM latest
                WHERE EXISTS (
                    SELECT 1
                    FROM market_snapshots ms
                    WHERE ms.condition_id = latest.condition_id
                      AND ms.snapshot_ts <= (latest.latest_snapshot_ts::timestamp - interval '{hours} hours')::text
                )
                """,
                tuple(condition_ids),
            )
            row = cur.fetchone()
            return int(row["n"]) if row else 0

    def insert_market_snapshot(self, row: Dict[str, Any]) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO market_snapshots (
                    condition_id, snapshot_ts, yes_price, no_price, yes_side, no_side,
                    yes_holder_count, no_holder_count, yes_top_holder_amount, no_top_holder_amount,
                    yes_top5_seen_share, no_top5_seen_share, observed_holder_wallets, raw_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (condition_id, snapshot_ts) DO UPDATE SET
                    yes_price=EXCLUDED.yes_price,
                    no_price=EXCLUDED.no_price,
                    yes_side=EXCLUDED.yes_side,
                    no_side=EXCLUDED.no_side,
                    yes_holder_count=EXCLUDED.yes_holder_count,
                    no_holder_count=EXCLUDED.no_holder_count,
                    yes_top_holder_amount=EXCLUDED.yes_top_holder_amount,
                    no_top_holder_amount=EXCLUDED.no_top_holder_amount,
                    yes_top5_seen_share=EXCLUDED.yes_top5_seen_share,
                    no_top5_seen_share=EXCLUDED.no_top5_seen_share,
                    observed_holder_wallets=EXCLUDED.observed_holder_wallets,
                    raw_json=EXCLUDED.raw_json
                """,
                (
                    row["condition_id"],
                    row["snapshot_ts"],
                    row.get("yes_price"),
                    row.get("no_price"),
                    row.get("yes_side"),
                    row.get("no_side"),
                    row.get("yes_holder_count"),
                    row.get("no_holder_count"),
                    row.get("yes_top_holder_amount"),
                    row.get("no_top_holder_amount"),
                    row.get("yes_top5_seen_share"),
                    row.get("no_top5_seen_share"),
                    row.get("observed_holder_wallets"),
                    safe_json_dumps(row.get("raw_json", {})),
                ),
            )

    def insert_holder_snapshot_rows(self, rows: Iterable[Dict[str, Any]]) -> None:
        with self.conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO holder_snapshots (
                    condition_id, snapshot_ts, token_id, wallet_address, amount, outcome_index, rank, raw_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (condition_id, snapshot_ts, token_id, wallet_address) DO UPDATE SET
                    amount=EXCLUDED.amount,
                    outcome_index=EXCLUDED.outcome_index,
                    rank=EXCLUDED.rank,
                    raw_json=EXCLUDED.raw_json
                """,
                [
                    (
                        row["condition_id"],
                        row["snapshot_ts"],
                        row["token_id"],
                        row["wallet_address"],
                        row.get("amount"),
                        row.get("outcome_index"),
                        row.get("rank"),
                        safe_json_dumps(row.get("raw_json", {})),
                    )
                    for row in rows
                ],
            )

    def insert_trades(self, rows: Iterable[Dict[str, Any]]) -> None:
        with self.conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO trades (
                    trade_key, trade_ts, condition_id, token_id, wallet_address, side,
                    price, size, notional, tx_hash, title, outcome, raw_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (trade_key) DO UPDATE SET
                    trade_ts=EXCLUDED.trade_ts,
                    condition_id=EXCLUDED.condition_id,
                    token_id=EXCLUDED.token_id,
                    wallet_address=EXCLUDED.wallet_address,
                    side=EXCLUDED.side,
                    price=EXCLUDED.price,
                    size=EXCLUDED.size,
                    notional=EXCLUDED.notional,
                    tx_hash=EXCLUDED.tx_hash,
                    title=EXCLUDED.title,
                    outcome=EXCLUDED.outcome,
                    raw_json=EXCLUDED.raw_json
                """,
                [
                    (
                        row["trade_key"],
                        row["trade_ts"],
                        row.get("condition_id"),
                        row.get("token_id"),
                        row.get("wallet_address"),
                        row.get("side"),
                        row.get("price"),
                        row.get("size"),
                        row.get("notional"),
                        row.get("tx_hash"),
                        row.get("title"),
                        row.get("outcome"),
                        safe_json_dumps(row.get("raw_json", {})),
                    )
                    for row in rows
                ],
            )

    def upsert_wallet_score(
        self,
        *,
        wallet_address: str,
        snapshot_ts: str,
        category: str,
        time_period: str,
        order_by: str,
        rank: int | None,
        score_value: float | None,
        raw_json: Dict[str, Any],
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO wallet_scores (
                    wallet_address, first_seen_ts, last_seen_ts, raw_json
                ) VALUES (%s, %s, %s, %s)
                ON CONFLICT (wallet_address) DO NOTHING
                """,
                (wallet_address, snapshot_ts, snapshot_ts, safe_json_dumps(raw_json)),
            )
            cur.execute(
                """
                UPDATE wallet_scores
                SET last_seen_ts=%s, raw_json=%s
                WHERE wallet_address=%s
                """,
                (snapshot_ts, safe_json_dumps(raw_json), wallet_address),
            )
            cur.execute(
                """
                INSERT INTO wallet_score_history (
                    wallet_address, snapshot_ts, category, time_period, order_by, rank, score_value, raw_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (wallet_address, snapshot_ts, category, time_period, order_by) DO UPDATE SET
                    rank=EXCLUDED.rank,
                    score_value=EXCLUDED.score_value,
                    raw_json=EXCLUDED.raw_json
                """,
                (wallet_address, snapshot_ts, category, time_period, order_by, rank, score_value, safe_json_dumps(raw_json)),
            )

    def update_wallet_summary_fields(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                WITH politics_pnl AS (
                    SELECT wallet_address, MIN(rank) AS best_rank
                    FROM wallet_score_history
                    WHERE category='POLITICS' AND order_by='PNL'
                    GROUP BY wallet_address
                ),
                politics_vol AS (
                    SELECT wallet_address, MIN(rank) AS best_rank
                    FROM wallet_score_history
                    WHERE category='POLITICS' AND order_by='VOL'
                    GROUP BY wallet_address
                ),
                overall_pnl AS (
                    SELECT wallet_address, MIN(rank) AS best_rank
                    FROM wallet_score_history
                    WHERE category='OVERALL' AND order_by='PNL'
                    GROUP BY wallet_address
                ),
                overall_vol AS (
                    SELECT wallet_address, MIN(rank) AS best_rank
                    FROM wallet_score_history
                    WHERE category='OVERALL' AND order_by='VOL'
                    GROUP BY wallet_address
                )
                UPDATE wallet_scores
                SET
                    politics_pnl_rank = (SELECT best_rank FROM politics_pnl WHERE politics_pnl.wallet_address = wallet_scores.wallet_address),
                    politics_vol_rank = (SELECT best_rank FROM politics_vol WHERE politics_vol.wallet_address = wallet_scores.wallet_address),
                    overall_pnl_rank = (SELECT best_rank FROM overall_pnl WHERE overall_pnl.wallet_address = wallet_scores.wallet_address),
                    overall_vol_rank = (SELECT best_rank FROM overall_vol WHERE overall_vol.wallet_address = wallet_scores.wallet_address)
                """
            )
            cur.execute(
                """
                UPDATE wallet_scores
                SET politics_score =
                    CASE
                        WHEN politics_pnl_rank IS NULL THEN NULL
                        ELSE (101 - politics_pnl_rank) + COALESCE((101 - politics_vol_rank) * 0.35, 0)
                    END,
                    overall_score =
                    CASE
                        WHEN overall_pnl_rank IS NULL THEN NULL
                        ELSE (101 - overall_pnl_rank) + COALESCE((101 - overall_vol_rank) * 0.35, 0)
                    END
                """
            )

    def get_wallet_scores(self, wallet_addresses: Sequence[str]) -> Dict[str, Dict[str, Any]]:
        if not wallet_addresses:
            return {}
        placeholders = ",".join("%s" for _ in wallet_addresses)
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM wallet_scores WHERE wallet_address IN ({placeholders})",
                tuple(wallet_addresses),
            )
            return {row["wallet_address"]: row for row in cur.fetchall()}

    def get_latest_snapshot(self, condition_id: str) -> Dict[str, Any] | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM market_snapshots
                WHERE condition_id = %s
                ORDER BY snapshot_ts DESC
                LIMIT 1
                """,
                (condition_id,),
            )
            return cur.fetchone()

    def get_snapshot_before(self, condition_id: str, base_ts: str, hours: int) -> Dict[str, Any] | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM market_snapshots
                WHERE condition_id = %s
                  AND snapshot_ts <= (%s::timestamp - interval '1 hour' * %s)::text
                ORDER BY snapshot_ts DESC
                LIMIT 1
                """,
                (condition_id, base_ts, hours),
            )
            return cur.fetchone()

    def get_snapshot_before_hours(self, condition_id: str, hours: int) -> Dict[str, Any] | None:
        return self.get_snapshot_before(condition_id, utc_now_iso(), hours)

    def get_latest_holder_addresses(self, condition_id: str) -> List[str]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT wallet_address
                FROM holder_snapshots
                WHERE condition_id = %s
                  AND snapshot_ts = (
                    SELECT MAX(snapshot_ts) FROM holder_snapshots WHERE condition_id = %s
                  )
                """,
                (condition_id, condition_id),
            )
            return [row["wallet_address"] for row in cur.fetchall()]

    def get_holder_addresses_before(self, condition_id: str, base_ts: str, hours: int) -> List[str]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT wallet_address
                FROM holder_snapshots
                WHERE condition_id = %s
                  AND snapshot_ts = (
                    SELECT MAX(snapshot_ts)
                    FROM holder_snapshots
                    WHERE condition_id = %s
                      AND snapshot_ts <= (%s::timestamp - interval '1 hour' * %s)::text
                  )
                """,
                (condition_id, condition_id, base_ts, hours),
            )
            return [row["wallet_address"] for row in cur.fetchall()]

    def get_holder_addresses_before_hours(self, condition_id: str, hours: int) -> List[str]:
        return self.get_holder_addresses_before(condition_id, utc_now_iso(), hours)

    def _backfill_recommendations_if_empty(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM recommendations")
            recommendation_count = int(cur.fetchone()["n"] or 0)
        if recommendation_count > 0:
            return

        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    wc.*,
                    COALESCE(
                        m.market_url,
                        CASE
                            WHEN COALESCE(m.event_slug, m.slug) IS NOT NULL
                            THEN 'https://polymarket.com/event/' || COALESCE(m.event_slug, m.slug)
                        END
                    ) AS market_url
                FROM watchlist_candidates wc
                LEFT JOIN markets m ON m.condition_id = wc.condition_id
                ORDER BY wc.snapshot_ts ASC, wc.condition_id ASC
                """
            )
            watchlist_rows = list(cur.fetchall())
        for row in watchlist_rows:
            payload = dict(row)
            payload["component_flags_json"] = row.get("component_flags_json")
            self.insert_recommendation(recommendation_from_watchlist(payload))

        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM alerts
                ORDER BY alert_ts ASC, id ASC
                """
            )
            alert_rows = list(cur.fetchall())
        for row in alert_rows:
            alert = Alert(
                condition_id=row["condition_id"],
                alert_type=row["alert_type"],
                score=row["score"],
                score_total=row["score_total"],
                score_price_anomaly=row["score_price_anomaly"],
                score_holder_concentration=row["score_holder_concentration"],
                score_wallet_quality=row["score_wallet_quality"],
                score_trade_flow=row["score_trade_flow"],
                market_title=row["market_title"],
                market_url=row["market_url"],
                yes_token_id=row["yes_token_id"],
                current_yes_price=row["current_yes_price"],
                price_delta_6h=row["price_delta_6h"],
                price_delta_24h=row["price_delta_24h"],
                price_delta_72h=row["price_delta_72h"],
                severity=row["severity"],
                confidence=row["confidence"],
                action_label=row["action_label"],
                reason_summary=row["reason_summary"] or row["summary"],
                summary=row["summary"],
                reasons_json=row["reasons_json"],
            )
            self.insert_recommendation(recommendation_from_alert(alert, alert_ts=row["alert_ts"]))

    def insert_alert(self, alert: Alert, alert_ts: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO alerts (
                    alert_ts, condition_id, alert_type, score, score_total, score_price_anomaly,
                    score_holder_concentration, score_wallet_quality, score_trade_flow, market_title,
                    market_url, yes_token_id, current_yes_price, price_delta_6h, price_delta_24h,
                    price_delta_72h, severity, confidence, action_label, reason_summary, summary, reasons_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    alert_ts,
                    alert.condition_id,
                    alert.alert_type,
                    alert.score,
                    alert.score_total,
                    alert.score_price_anomaly,
                    alert.score_holder_concentration,
                    alert.score_wallet_quality,
                    alert.score_trade_flow,
                    alert.market_title,
                    alert.market_url,
                    alert.yes_token_id,
                    alert.current_yes_price,
                    alert.price_delta_6h,
                    alert.price_delta_24h,
                    alert.price_delta_72h,
                    alert.severity,
                    alert.confidence,
                    alert.action_label,
                    alert.reason_summary,
                    alert.summary,
                    alert.reasons_json,
                ),
            )

    def insert_recommendation(self, row: Dict[str, Any]) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO recommendations (
                    entry_ts, condition_id, source, market_title, market_url, side, recommendation,
                    status, conviction_score, severity, confidence, reason_summary, entry_price, entry_yes_price,
                    history_ready_6h, warmup_only, trade_enriched, source_meta_json, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (condition_id, source, entry_ts) DO UPDATE SET
                    market_title=EXCLUDED.market_title,
                    market_url=EXCLUDED.market_url,
                    side=EXCLUDED.side,
                    recommendation=EXCLUDED.recommendation,
                    status=EXCLUDED.status,
                    conviction_score=EXCLUDED.conviction_score,
                    severity=EXCLUDED.severity,
                    confidence=EXCLUDED.confidence,
                    reason_summary=EXCLUDED.reason_summary,
                    entry_price=EXCLUDED.entry_price,
                    entry_yes_price=EXCLUDED.entry_yes_price,
                    history_ready_6h=EXCLUDED.history_ready_6h,
                    warmup_only=EXCLUDED.warmup_only,
                    trade_enriched=EXCLUDED.trade_enriched,
                    source_meta_json=EXCLUDED.source_meta_json
                """,
                (
                    row["entry_ts"],
                    row["condition_id"],
                    row["source"],
                    row.get("market_title"),
                    row.get("market_url"),
                    row.get("side", "Yes"),
                    row["recommendation"],
                    row["status"],
                    row.get("conviction_score", 0.0),
                    row.get("severity"),
                    row.get("confidence"),
                    row.get("reason_summary"),
                    row.get("entry_price", row.get("entry_yes_price")),
                    row.get("entry_yes_price"),
                    int(bool(row.get("history_ready_6h"))),
                    int(bool(row.get("warmup_only"))),
                    int(bool(row.get("trade_enriched"))),
                    row.get("source_meta_json") or safe_json_dumps({}),
                    row.get("created_at") or utc_now_iso(),
                ),
            )

    def insert_watchlist_candidate(self, row: Dict[str, Any]) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO watchlist_candidates (
                    snapshot_ts, condition_id, market_title, side, current_yes_price, current_no_price,
                    price_delta_6h, no_price_delta_6h, yes_top5_seen_share, no_top5_seen_share,
                    price_anomaly_hit, holder_concentration_hit,
                    wallet_quality_hit, warmup_only, history_ready_6h, trade_enriched,
                    reason_summary, component_flags_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (condition_id, snapshot_ts) DO UPDATE SET
                    market_title=EXCLUDED.market_title,
                    side=EXCLUDED.side,
                    current_yes_price=EXCLUDED.current_yes_price,
                    current_no_price=EXCLUDED.current_no_price,
                    price_delta_6h=EXCLUDED.price_delta_6h,
                    no_price_delta_6h=EXCLUDED.no_price_delta_6h,
                    yes_top5_seen_share=EXCLUDED.yes_top5_seen_share,
                    no_top5_seen_share=EXCLUDED.no_top5_seen_share,
                    price_anomaly_hit=EXCLUDED.price_anomaly_hit,
                    holder_concentration_hit=EXCLUDED.holder_concentration_hit,
                    wallet_quality_hit=EXCLUDED.wallet_quality_hit,
                    warmup_only=EXCLUDED.warmup_only,
                    history_ready_6h=EXCLUDED.history_ready_6h,
                    trade_enriched=EXCLUDED.trade_enriched,
                    reason_summary=EXCLUDED.reason_summary,
                    component_flags_json=EXCLUDED.component_flags_json
                """,
                (
                    row["snapshot_ts"],
                    row["condition_id"],
                    row.get("market_title"),
                    row.get("side", "Yes"),
                    row.get("current_yes_price"),
                    row.get("current_no_price"),
                    row.get("price_delta_6h"),
                    row.get("no_price_delta_6h"),
                    row.get("yes_top5_seen_share"),
                    row.get("no_top5_seen_share"),
                    int(bool(row.get("price_anomaly_hit"))),
                    int(bool(row.get("holder_concentration_hit"))),
                    int(bool(row.get("wallet_quality_hit"))),
                    int(bool(row.get("warmup_only"))),
                    int(bool(row.get("history_ready_6h"))),
                    int(bool(row.get("trade_enriched"))),
                    row.get("reason_summary"),
                    safe_json_dumps(row.get("component_flags_json", {})),
                ),
            )

    def start_job_run(self, job_name: str, started_at: str) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO job_runs (job_name, started_at, status)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (job_name, started_at, "running"),
            )
            row = cur.fetchone()
            return int(row["id"])

    def finish_job_run(
        self,
        job_run_id: int,
        *,
        finished_at: str,
        status: str,
        rows_written: int | None = None,
        meta: Dict[str, Any] | None = None,
        error_text: str | None = None,
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE job_runs
                SET finished_at = %s, status = %s, rows_written = %s, meta_json = %s, error_text = %s
                WHERE id = %s
                """,
                (
                    finished_at,
                    status,
                    rows_written,
                    safe_json_dumps(meta or {}),
                    error_text,
                    job_run_id,
                ),
            )

    def get_unsent_alerts(self) -> List[Dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.*, COALESCE(m.title, a.market_title) AS title
                FROM alerts a
                LEFT JOIN markets m ON m.condition_id = a.condition_id
                WHERE sent = 0
                ORDER BY alert_ts ASC
                """
            )
            return list(cur.fetchall())

    def mark_alert_sent(self, alert_id: int) -> None:
        with self.conn.cursor() as cur:
            cur.execute("UPDATE alerts SET sent = 1 WHERE id = %s", (alert_id,))

    def get_alerts(self) -> List[Dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM alerts ORDER BY alert_ts ASC")
            return list(cur.fetchall())

    def count_backtestable_alerts(self, hours_forward: int) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS n
                FROM alerts a
                LEFT JOIN markets m ON m.condition_id = a.condition_id
                WHERE a.alert_ts <= (NOW() AT TIME ZONE 'UTC' - interval '1 hour' * %s)::text
                  AND (
                    m.yes_token_id IS NOT NULL
                    OR EXISTS (
                        SELECT 1
                        FROM market_snapshots ms
                        WHERE ms.condition_id = a.condition_id
                          AND ms.snapshot_ts >= a.alert_ts
                    )
                  )
                """,
                (hours_forward,),
            )
            row = cur.fetchone()
            return int(row["n"]) if row else 0

    def get_snapshot_at_or_after(self, condition_id: str, hours_forward: int, base_ts: str) -> Dict[str, Any] | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM market_snapshots
                WHERE condition_id = %s
                  AND snapshot_ts >= (%s::timestamp + interval '1 hour' * %s)::text
                ORDER BY snapshot_ts ASC
                LIMIT 1
                """,
                (condition_id, base_ts, hours_forward),
            )
            return cur.fetchone()

    def get_market_title(self, condition_id: str) -> str | None:
        with self.conn.cursor() as cur:
            cur.execute("SELECT title FROM markets WHERE condition_id = %s", (condition_id,))
            row = cur.fetchone()
            return row["title"] if row else None

    def get_market_backtest_meta(self, condition_id: str) -> Dict[str, Any] | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT condition_id, title, yes_token_id, no_token_id
                FROM markets
                WHERE condition_id = %s
                """,
                (condition_id,),
            )
            return cur.fetchone()

    def get_recent_trades(self, condition_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM trades
                WHERE condition_id = %s
                ORDER BY trade_ts DESC, trade_key DESC
                LIMIT %s
                """,
                (condition_id, limit),
            )
            return list(cur.fetchall())
