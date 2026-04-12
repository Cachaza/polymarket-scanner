from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from .models import Alert, MarketRecord
from .utils import safe_json_dumps, utc_now_iso


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def init_schema(self, schema_path: Path) -> None:
        sql = schema_path.read_text(encoding="utf-8")
        self.conn.executescript(sql)
        self._migrate_schema()
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def _table_columns(self, table_name: str) -> set[str]:
        cur = self.conn.execute(f"PRAGMA table_info({table_name})")
        return {row["name"] for row in cur.fetchall()}

    def _ensure_column(self, table_name: str, column_name: str, definition: str) -> None:
        columns = self._table_columns(table_name)
        if column_name in columns:
            return
        self.conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

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

        self.conn.execute(
            """
            UPDATE markets
            SET
                market_id = COALESCE(market_id, json_extract(raw_json, '$.id')),
                question_id = COALESCE(question_id, json_extract(raw_json, '$.questionID')),
                market_url = COALESCE(
                    market_url,
                    CASE
                        WHEN COALESCE(event_slug, slug) IS NOT NULL
                        THEN 'https://polymarket.com/event/' || COALESCE(event_slug, slug)
                    END
                ),
                accepting_orders = COALESCE(accepting_orders, json_extract(raw_json, '$.acceptingOrders')),
                end_date = COALESCE(
                    end_date,
                    json_extract(raw_json, '$.endDate'),
                    json_extract(raw_json, '$.umaEndDate'),
                    json_extract(raw_json, '$.closedTime')
                ),
                closed_time = COALESCE(closed_time, json_extract(raw_json, '$.closedTime')),
                image_url = COALESCE(
                    image_url,
                    json_extract(raw_json, '$.image'),
                    json_extract(raw_json, '$.icon')
                ),
                reward_asset_address = COALESCE(
                    reward_asset_address,
                    json_extract(raw_json, '$.clobRewards[0].assetAddress')
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

        self.conn.execute(
            '''
            UPDATE alerts
            SET
                score_total = CASE
                    WHEN score_total = 0 AND score IS NOT NULL THEN score
                    ELSE score_total
                END,
                reason_summary = COALESCE(reason_summary, summary)
            '''
        )

    def upsert_event(self, event: Dict[str, Any]) -> None:
        self.conn.execute(
            '''
            INSERT INTO events (
                event_id, slug, title, description, category, subcategory, active, closed, archived,
                liquidity, volume, volume24hr, open_interest, end_date, updated_at, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO UPDATE SET
                slug=excluded.slug,
                title=excluded.title,
                description=excluded.description,
                category=excluded.category,
                subcategory=excluded.subcategory,
                active=excluded.active,
                closed=excluded.closed,
                archived=excluded.archived,
                liquidity=excluded.liquidity,
                volume=excluded.volume,
                volume24hr=excluded.volume24hr,
                open_interest=excluded.open_interest,
                end_date=excluded.end_date,
                updated_at=excluded.updated_at,
                raw_json=excluded.raw_json
            ''',
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
        self.conn.execute(
            '''
            INSERT INTO markets (
                condition_id, event_id, event_slug, slug, market_id, question_id, market_url, title, description, category,
                active, closed, archived, accepting_orders, end_date, closed_time, yes_token_id, no_token_id, image_url,
                reward_asset_address, discovered_at, last_seen_at, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(condition_id) DO UPDATE SET
                event_id=excluded.event_id,
                event_slug=excluded.event_slug,
                slug=excluded.slug,
                market_id=excluded.market_id,
                question_id=excluded.question_id,
                market_url=excluded.market_url,
                title=excluded.title,
                description=excluded.description,
                category=excluded.category,
                active=excluded.active,
                closed=excluded.closed,
                archived=excluded.archived,
                accepting_orders=excluded.accepting_orders,
                end_date=excluded.end_date,
                closed_time=excluded.closed_time,
                yes_token_id=excluded.yes_token_id,
                no_token_id=excluded.no_token_id,
                image_url=excluded.image_url,
                reward_asset_address=excluded.reward_asset_address,
                last_seen_at=excluded.last_seen_at,
                raw_json=excluded.raw_json
            ''',
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

    def get_active_markets(self, limit: int = 250) -> List[sqlite3.Row]:
        cur = self.conn.execute(
            '''
            SELECT *
            FROM markets
            WHERE active = 1 AND closed = 0
            ORDER BY rowid DESC
            LIMIT ?
            ''',
            (limit,),
        )
        return list(cur.fetchall())

    def get_market_count(self) -> int:
        cur = self.conn.execute("SELECT COUNT(*) AS n FROM markets")
        row = cur.fetchone()
        return int(row["n"]) if row else 0

    def get_snapshot_bounds(self) -> sqlite3.Row | None:
        cur = self.conn.execute(
            '''
            SELECT
                MIN(snapshot_ts) AS first_snapshot_ts,
                MAX(snapshot_ts) AS latest_snapshot_ts,
                COUNT(*) AS snapshot_rows,
                COUNT(DISTINCT condition_id) AS snapshot_markets
            FROM market_snapshots
            '''
        )
        return cur.fetchone()

    def count_history_ready_markets(self, condition_ids: Sequence[str], hours: int) -> int:
        if not condition_ids:
            return 0
        placeholders = ",".join("?" for _ in condition_ids)
        cur = self.conn.execute(
            f'''
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
                  AND ms.snapshot_ts <= datetime(latest.latest_snapshot_ts, ?)
            )
            ''',
            tuple(condition_ids) + (f"-{hours} hours",),
        )
        row = cur.fetchone()
        return int(row["n"]) if row else 0

    def insert_market_snapshot(self, row: Dict[str, Any]) -> None:
        self.conn.execute(
            '''
            INSERT OR REPLACE INTO market_snapshots (
                condition_id, snapshot_ts, yes_price, no_price, yes_side, no_side,
                yes_holder_count, no_holder_count, yes_top_holder_amount, no_top_holder_amount,
                yes_top5_seen_share, no_top5_seen_share, observed_holder_wallets, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
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
        self.conn.executemany(
            '''
            INSERT OR REPLACE INTO holder_snapshots (
                condition_id, snapshot_ts, token_id, wallet_address, amount, outcome_index, rank, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
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
        self.conn.executemany(
            '''
            INSERT OR REPLACE INTO trades (
                trade_key, trade_ts, condition_id, token_id, wallet_address, side,
                price, size, notional, tx_hash, title, outcome, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
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
        self.conn.execute(
            '''
            INSERT OR IGNORE INTO wallet_scores (
                wallet_address, first_seen_ts, last_seen_ts, raw_json
            ) VALUES (?, ?, ?, ?)
            ''',
            (wallet_address, snapshot_ts, snapshot_ts, safe_json_dumps(raw_json)),
        )
        self.conn.execute(
            '''
            UPDATE wallet_scores
            SET last_seen_ts=?, raw_json=?
            WHERE wallet_address=?
            ''',
            (snapshot_ts, safe_json_dumps(raw_json), wallet_address),
        )
        self.conn.execute(
            '''
            INSERT OR REPLACE INTO wallet_score_history (
                wallet_address, snapshot_ts, category, time_period, order_by, rank, score_value, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (wallet_address, snapshot_ts, category, time_period, order_by, rank, score_value, safe_json_dumps(raw_json)),
        )

    def update_wallet_summary_fields(self) -> None:
        self.conn.executescript(
            '''
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
                overall_vol_rank = (SELECT best_rank FROM overall_vol WHERE overall_vol.wallet_address = wallet_scores.wallet_address);
            '''
        )
        self.conn.execute(
            '''
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
            '''
        )

    def get_wallet_scores(self, wallet_addresses: Sequence[str]) -> Dict[str, sqlite3.Row]:
        if not wallet_addresses:
            return {}
        placeholders = ",".join("?" for _ in wallet_addresses)
        cur = self.conn.execute(
            f"SELECT * FROM wallet_scores WHERE wallet_address IN ({placeholders})",
            tuple(wallet_addresses),
        )
        return {row["wallet_address"]: row for row in cur.fetchall()}

    def get_latest_snapshot(self, condition_id: str) -> sqlite3.Row | None:
        cur = self.conn.execute(
            '''
            SELECT * FROM market_snapshots
            WHERE condition_id = ?
            ORDER BY snapshot_ts DESC
            LIMIT 1
            ''',
            (condition_id,),
        )
        return cur.fetchone()

    def get_snapshot_before(self, condition_id: str, base_ts: str, hours: int) -> sqlite3.Row | None:
        cur = self.conn.execute(
            '''
            SELECT *
            FROM market_snapshots
            WHERE condition_id = ?
              AND snapshot_ts <= datetime(?, ?)
            ORDER BY snapshot_ts DESC
            LIMIT 1
            ''',
            (condition_id, base_ts, f"-{hours} hours"),
        )
        return cur.fetchone()

    def get_snapshot_before_hours(self, condition_id: str, hours: int) -> sqlite3.Row | None:
        return self.get_snapshot_before(condition_id, utc_now_iso(), hours)

    def get_latest_holder_addresses(self, condition_id: str) -> List[str]:
        cur = self.conn.execute(
            '''
            SELECT wallet_address
            FROM holder_snapshots
            WHERE condition_id = ?
              AND snapshot_ts = (
                SELECT MAX(snapshot_ts) FROM holder_snapshots WHERE condition_id = ?
              )
            ''',
            (condition_id, condition_id),
        )
        return [row["wallet_address"] for row in cur.fetchall()]

    def get_holder_addresses_before(self, condition_id: str, base_ts: str, hours: int) -> List[str]:
        cur = self.conn.execute(
            '''
            SELECT wallet_address
            FROM holder_snapshots
            WHERE condition_id = ?
              AND snapshot_ts = (
                SELECT MAX(snapshot_ts)
                FROM holder_snapshots
                WHERE condition_id = ?
                  AND snapshot_ts <= datetime(?, ?)
              )
            ''',
            (condition_id, condition_id, base_ts, f"-{hours} hours"),
        )
        return [row["wallet_address"] for row in cur.fetchall()]

    def get_holder_addresses_before_hours(self, condition_id: str, hours: int) -> List[str]:
        return self.get_holder_addresses_before(condition_id, utc_now_iso(), hours)

    def insert_alert(self, alert: Alert, alert_ts: str) -> None:
        self.conn.execute(
            '''
            INSERT INTO alerts (
                alert_ts, condition_id, alert_type, score, score_total, score_price_anomaly,
                score_holder_concentration, score_wallet_quality, score_trade_flow, market_title,
                market_url, yes_token_id, current_yes_price, price_delta_6h, price_delta_24h,
                price_delta_72h, severity, confidence, action_label, reason_summary, summary, reasons_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
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

    def insert_watchlist_candidate(self, row: Dict[str, Any]) -> None:
        self.conn.execute(
            '''
            INSERT OR REPLACE INTO watchlist_candidates (
                snapshot_ts, condition_id, market_title, current_yes_price, price_delta_6h,
                yes_top5_seen_share, price_anomaly_hit, holder_concentration_hit,
                wallet_quality_hit, warmup_only, history_ready_6h, trade_enriched,
                reason_summary, component_flags_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                row["snapshot_ts"],
                row["condition_id"],
                row.get("market_title"),
                row.get("current_yes_price"),
                row.get("price_delta_6h"),
                row.get("yes_top5_seen_share"),
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
        cur = self.conn.execute(
            '''
            INSERT INTO job_runs (job_name, started_at, status)
            VALUES (?, ?, ?)
            ''',
            (job_name, started_at, "running"),
        )
        return int(cur.lastrowid)

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
        self.conn.execute(
            '''
            UPDATE job_runs
            SET finished_at = ?, status = ?, rows_written = ?, meta_json = ?, error_text = ?
            WHERE id = ?
            ''',
            (
                finished_at,
                status,
                rows_written,
                safe_json_dumps(meta or {}),
                error_text,
                job_run_id,
            ),
        )

    def get_unsent_alerts(self) -> List[sqlite3.Row]:
        cur = self.conn.execute(
            '''
            SELECT a.*, COALESCE(m.title, a.market_title) AS title
            FROM alerts a
            LEFT JOIN markets m ON m.condition_id = a.condition_id
            WHERE sent = 0
            ORDER BY alert_ts ASC
            '''
        )
        return list(cur.fetchall())

    def mark_alert_sent(self, alert_id: int) -> None:
        self.conn.execute("UPDATE alerts SET sent = 1 WHERE id = ?", (alert_id,))

    def get_alerts(self) -> List[sqlite3.Row]:
        cur = self.conn.execute("SELECT * FROM alerts ORDER BY alert_ts ASC")
        return list(cur.fetchall())

    def count_backtestable_alerts(self, hours_forward: int) -> int:
        cur = self.conn.execute(
            '''
            SELECT COUNT(*) AS n
            FROM alerts a
            LEFT JOIN markets m ON m.condition_id = a.condition_id
            WHERE a.alert_ts <= datetime('now', ?)
              AND (
                m.yes_token_id IS NOT NULL
                OR EXISTS (
                    SELECT 1
                    FROM market_snapshots ms
                    WHERE ms.condition_id = a.condition_id
                      AND ms.snapshot_ts >= a.alert_ts
                )
              )
            ''',
            (f"-{hours_forward} hours",),
        )
        row = cur.fetchone()
        return int(row["n"]) if row else 0

    def get_snapshot_at_or_after(self, condition_id: str, hours_forward: int, base_ts: str) -> sqlite3.Row | None:
        cur = self.conn.execute(
            '''
            SELECT *
            FROM market_snapshots
            WHERE condition_id = ?
              AND snapshot_ts >= datetime(?, ?)
            ORDER BY snapshot_ts ASC
            LIMIT 1
            ''',
            (condition_id, base_ts, f"+{hours_forward} hours"),
        )
        return cur.fetchone()

    def get_market_title(self, condition_id: str) -> str | None:
        cur = self.conn.execute("SELECT title FROM markets WHERE condition_id = ?", (condition_id,))
        row = cur.fetchone()
        return row["title"] if row else None

    def get_market_backtest_meta(self, condition_id: str) -> sqlite3.Row | None:
        cur = self.conn.execute(
            '''
            SELECT condition_id, title, yes_token_id, no_token_id
            FROM markets
            WHERE condition_id = ?
            ''',
            (condition_id,),
        )
        return cur.fetchone()

    def get_recent_trades(self, condition_id: str, limit: int = 50) -> List[sqlite3.Row]:
        cur = self.conn.execute(
            '''
            SELECT *
            FROM trades
            WHERE condition_id = ?
            ORDER BY trade_ts DESC, trade_key DESC
            LIMIT ?
            ''',
            (condition_id, limit),
        )
        return list(cur.fetchall())
