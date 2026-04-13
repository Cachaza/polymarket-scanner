from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api_server import app
from app.backtest import run_latent_entry_backtest
from app.config import Settings
from app.db import Database
from app.read_service import (
    get_market_trade_aftermath,
    get_overview,
    get_watchlist,
    list_alerts,
    list_recommendations,
)


def _build_fixture_db(tmp_path: Path) -> Settings:
    db_path = tmp_path / "fixture.sqlite"
    backtest_csv_path = tmp_path / "backtest.csv"
    latent_backtest_csv_path = tmp_path / "latent_backtest.csv"
    backtest_csv_path.write_text("alert_ts,condition_id,title,alert_type,score,entry_yes_price,fwd_24h_yes_return,fwd_24h_yes_price\n", encoding="utf-8")

    db = Database(db_path)
    try:
        schema_path = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"
        db.init_schema(schema_path)
        db.conn.execute(
            """
            INSERT INTO events (
                event_id, slug, title, description, category, subcategory, active, closed, archived,
                liquidity, volume, volume24hr, open_interest, end_date, updated_at, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "event-1",
                "event-slug",
                "Fixture Event",
                "fixture event",
                "Politics",
                "Election",
                1,
                0,
                0,
                1000,
                500,
                200,
                100,
                "2026-04-10 00:00:00",
                "2026-04-09 00:00:00",
                "{}",
            ),
        )
        db.conn.execute(
            """
            INSERT INTO markets (
                condition_id, event_id, event_slug, slug, market_id, question_id, market_url, title, description, category,
                active, closed, archived, accepting_orders, end_date, closed_time, yes_token_id, no_token_id, image_url,
                reward_asset_address, discovered_at, last_seen_at, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "cond-1",
                "event-1",
                "event-slug",
                "market-slug",
                "market-1",
                "question-1",
                "https://polymarket.com/event/event-slug",
                "Fixture Market",
                "fixture",
                "Politics",
                1,
                0,
                0,
                1,
                "2026-04-10 00:00:00",
                None,
                "yes-token",
                "no-token",
                "https://example.com/market.png",
                "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
                "2026-04-09 00:00:00",
                "2026-04-09 06:30:00",
                "{}",
            ),
        )
        db.conn.execute(
            """
            INSERT INTO markets (
                condition_id, event_id, event_slug, slug, market_id, question_id, market_url, title, description, category,
                active, closed, archived, accepting_orders, end_date, closed_time, yes_token_id, no_token_id, image_url,
                reward_asset_address, discovered_at, last_seen_at, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "cond-3",
                "event-1",
                "event-slug",
                "latent-market-slug",
                "market-3",
                "question-3",
                "https://polymarket.com/event/event-slug",
                "Latent Fixture Market",
                "fixture",
                "Politics",
                1,
                1,
                0,
                0,
                "2026-04-15 00:00:00",
                "2026-04-15 00:00:00",
                "yes-token-3",
                "no-token-3",
                None,
                None,
                "2026-04-10 00:00:00",
                "2026-04-15 00:00:00",
                "{}",
            ),
        )
        db.conn.execute(
            """
            INSERT INTO markets (
                condition_id, event_id, event_slug, slug, market_id, question_id, market_url, title, description, category,
                active, closed, archived, accepting_orders, end_date, closed_time, yes_token_id, no_token_id, image_url,
                reward_asset_address, discovered_at, last_seen_at, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "cond-2",
                "event-1",
                "event-slug",
                "closed-market-slug",
                "market-2",
                "question-2",
                "https://polymarket.com/event/event-slug",
                "Closed Fixture Market",
                "fixture",
                "Politics",
                1,
                1,
                0,
                0,
                "2026-04-08 00:00:00",
                "2026-04-08 02:00:00",
                "yes-token-2",
                "no-token-2",
                None,
                None,
                "2026-04-08 00:00:00",
                "2026-04-08 02:00:00",
                "{}",
            ),
        )
        db.conn.execute(
            """
            INSERT INTO market_snapshots (
                condition_id, snapshot_ts, yes_price, no_price, yes_side, no_side, yes_holder_count, no_holder_count,
                yes_top_holder_amount, no_top_holder_amount, yes_top5_seen_share, no_top5_seen_share, observed_holder_wallets, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("cond-1", "2026-04-09 00:00:00", 0.4, 0.6, "buy", "sell", 4, 4, 100, 80, 0.4, 0.3, 8, "{}"),
        )
        db.conn.execute(
            """
            INSERT INTO market_snapshots (
                condition_id, snapshot_ts, yes_price, no_price, yes_side, no_side, yes_holder_count, no_holder_count,
                yes_top_holder_amount, no_top_holder_amount, yes_top5_seen_share, no_top5_seen_share, observed_holder_wallets, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("cond-1", "2026-04-09 06:30:00", 0.52, 0.48, "buy", "sell", 6, 5, 120, 90, 0.66, 0.34, 12, "{}"),
        )
        db.conn.execute(
            """
            INSERT INTO market_snapshots (
                condition_id, snapshot_ts, yes_price, no_price, yes_side, no_side, yes_holder_count, no_holder_count,
                yes_top_holder_amount, no_top_holder_amount, yes_top5_seen_share, no_top5_seen_share, observed_holder_wallets, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("cond-1", "2026-04-10 01:00:00", 0.7, 0.3, "buy", "sell", 9, 7, 180, 110, 0.7, 0.3, 16, "{}"),
        )
        db.conn.execute(
            """
            INSERT INTO market_snapshots (
                condition_id, snapshot_ts, yes_price, no_price, yes_side, no_side, yes_holder_count, no_holder_count,
                yes_top_holder_amount, no_top_holder_amount, yes_top5_seen_share, no_top5_seen_share, observed_holder_wallets, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("cond-3", "2026-04-10 00:00:00", 0.34, 0.66, "buy", "sell", 4, 4, 90, 120, 0.41, 0.59, 8, "{}"),
        )
        db.conn.execute(
            """
            INSERT INTO market_snapshots (
                condition_id, snapshot_ts, yes_price, no_price, yes_side, no_side, yes_holder_count, no_holder_count,
                yes_top_holder_amount, no_top_holder_amount, yes_top5_seen_share, no_top5_seen_share, observed_holder_wallets, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("cond-3", "2026-04-11 00:30:00", 0.36, 0.64, "buy", "sell", 5, 5, 110, 130, 0.46, 0.54, 9, "{}"),
        )
        db.conn.execute(
            """
            INSERT INTO market_snapshots (
                condition_id, snapshot_ts, yes_price, no_price, yes_side, no_side, yes_holder_count, no_holder_count,
                yes_top_holder_amount, no_top_holder_amount, yes_top5_seen_share, no_top5_seen_share, observed_holder_wallets, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("cond-3", "2026-04-12 01:00:00", 0.79, 0.21, "buy", "sell", 8, 6, 260, 90, 0.58, 0.42, 13, "{}"),
        )
        db.conn.execute(
            """
            INSERT INTO holder_snapshots (
                condition_id, snapshot_ts, token_id, wallet_address, amount, outcome_index, rank, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("cond-1", "2026-04-09 06:30:00", "yes-token", "0xabc", 1200, 0, 1, "{}"),
        )
        db.conn.execute(
            """
            INSERT INTO holder_snapshots (
                condition_id, snapshot_ts, token_id, wallet_address, amount, outcome_index, rank, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("cond-3", "2026-04-11 00:30:00", "yes-token-3", "0xlatent", 3200, 0, 1, "{}"),
        )
        db.conn.execute(
            """
            INSERT INTO wallet_scores (
                wallet_address, first_seen_ts, last_seen_ts, politics_pnl_rank, politics_vol_rank, overall_pnl_rank,
                overall_vol_rank, politics_score, overall_score, notes, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("0xwhale", "2026-04-08 00:00:00", "2026-04-10 01:00:00", 7, 11, 21, 33, 88.5, 71.2, None, "{}"),
        )
        db.conn.execute(
            """
            INSERT INTO wallet_scores (
                wallet_address, first_seen_ts, last_seen_ts, politics_pnl_rank, politics_vol_rank, overall_pnl_rank,
                overall_vol_rank, politics_score, overall_score, notes, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("0xlatent", "2026-04-10 00:00:00", "2026-04-12 01:00:00", 4, 6, 18, 25, 91.4, 74.2, None, "{}"),
        )
        db.conn.execute(
            """
            INSERT INTO trades (
                trade_key, trade_ts, condition_id, token_id, wallet_address, side, price, size, notional, tx_hash, title, outcome, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "trade-big-buy",
                "2026-04-09 00:30:00",
                "cond-1",
                "yes-token",
                "0xwhale",
                "buy",
                0.41,
                5000,
                2050,
                "0xtxbig",
                "Fixture Market",
                "Yes",
                "{}",
            ),
        )
        db.conn.execute(
            """
            INSERT INTO trades (
                trade_key, trade_ts, condition_id, token_id, wallet_address, side, price, size, notional, tx_hash, title, outcome, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "latent-buy-1",
                "2026-04-10 00:15:00",
                "cond-3",
                "yes-token-3",
                "0xlatent",
                "buy",
                0.34,
                3000,
                1020,
                "0xlatent1",
                "Latent Fixture Market",
                "Yes",
                "{}",
            ),
        )
        db.conn.execute(
            """
            INSERT INTO trades (
                trade_key, trade_ts, condition_id, token_id, wallet_address, side, price, size, notional, tx_hash, title, outcome, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "latent-buy-2",
                "2026-04-10 12:00:00",
                "cond-3",
                "yes-token-3",
                "0xlatent",
                "buy",
                0.35,
                4800,
                1680,
                "0xlatent2",
                "Latent Fixture Market",
                "Yes",
                "{}",
            ),
        )
        db.conn.execute(
            """
            INSERT INTO trades (
                trade_key, trade_ts, condition_id, token_id, wallet_address, side, price, size, notional, tx_hash, title, outcome, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "trade-small-buy",
                "2026-04-09 00:45:00",
                "cond-1",
                "yes-token",
                "0xsmall",
                "buy",
                0.42,
                100,
                42,
                "0xtxsmall",
                "Fixture Market",
                "Yes",
                "{}",
            ),
        )
        db.conn.execute(
            """
            INSERT INTO watchlist_candidates (
                snapshot_ts, condition_id, market_title, current_yes_price, price_delta_6h, yes_top5_seen_share,
                price_anomaly_hit, holder_concentration_hit, wallet_quality_hit, warmup_only, history_ready_6h,
                trade_enriched, reason_summary, component_flags_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-04-09 06:30:00",
                "cond-1",
                "Fixture Market",
                0.52,
                0.12,
                0.66,
                1,
                0,
                1,
                0,
                1,
                1,
                "price anomaly, wallet quality (history-ready)",
                '{"price_anomaly": true, "wallet_quality": true, "history_ready_6h": true}',
            ),
        )
        db.conn.execute(
            """
            INSERT INTO job_runs (job_name, started_at, finished_at, status, rows_written, meta_json, error_text)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("snapshot", "2026-04-09 06:29:00", "2026-04-09 06:30:00", "completed", 1, '{"watchlist_candidates": 1}', None),
        )
        db.conn.execute(
            """
            INSERT INTO alerts (
                alert_ts, condition_id, alert_type, score, score_total, score_price_anomaly,
                score_holder_concentration, score_wallet_quality, score_trade_flow, market_title,
                market_url, yes_token_id, current_yes_price, price_delta_6h, price_delta_24h,
                price_delta_72h, severity, confidence, action_label, reason_summary, summary, reasons_json, sent
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-04-10 01:05:00",
                "cond-1",
                "smart_money",
                8.7,
                8.7,
                3.5,
                1.2,
                2.8,
                1.2,
                "Fixture Market",
                "https://polymarket.com/event/event-slug",
                "yes-token",
                0.7,
                0.18,
                0.3,
                None,
                "high",
                "medium",
                "Monitor",
                "price anomaly, wallet quality",
                "Fixture summary",
                '{"reason_summary":"price anomaly, wallet quality","reasons":["price anomaly","wallet quality"],"trigger_breakdown":{"price_anomaly":{"triggered":true}}}',
                0,
            ),
        )
        db.commit()
    finally:
        db.close()

    return Settings(
        db_path=db_path,
        backtest_csv_path=backtest_csv_path,
        latent_backtest_csv_path=latent_backtest_csv_path,
        market_limit=250,
    )


def test_read_service_overview_matches_fixture(tmp_path: Path) -> None:
    settings = _build_fixture_db(tmp_path)
    from app.read_db import read_connection

    with read_connection(settings.db_path) as conn:
        overview = get_overview(conn, settings)

    assert overview.markets_discovered == 3
    assert overview.active_scanner_scope == 1
    assert overview.markets_with_enough_6h_history == 1
    assert overview.watchlist_candidates == 1


def test_read_service_watchlist_persistence(tmp_path: Path) -> None:
    settings = _build_fixture_db(tmp_path)
    from app.read_db import read_connection

    with read_connection(settings.db_path) as conn:
        watchlist = get_watchlist(conn, warmup_only=False)

    assert watchlist.total == 1
    assert watchlist.items[0].history_ready_6h is True
    assert watchlist.items[0].trade_enriched is True


def test_read_service_trade_aftermath_uses_entry_and_forward_snapshots(tmp_path: Path) -> None:
    settings = _build_fixture_db(tmp_path)
    from app.read_db import read_connection

    with read_connection(settings.db_path) as conn:
        response = get_market_trade_aftermath(conn, "cond-1", limit=5, min_notional=1000, side="buy", outcome="Yes")

    assert response.total == 1
    assert len(response.items) == 1
    item = response.items[0]
    assert item.trade_key == "trade-big-buy"
    assert item.entry_snapshot_ts == "2026-04-09 00:00:00"
    assert item.entry_yes_price == 0.4
    assert item.current_yes_price == 0.7
    assert item.current_outcome_return == 0.7073
    assert item.horizons[0].target_hours == 6
    assert item.horizons[0].snapshot_ts == "2026-04-09 06:30:00"
    assert item.horizons[0].outcome_return == 0.2683
    assert item.horizons[1].snapshot_ts == "2026-04-10 01:00:00"
    assert item.politics_score == 88.5


def test_latent_backtest_detects_flat_pre_signal_accumulation(tmp_path: Path) -> None:
    settings = _build_fixture_db(tmp_path)
    db = Database(settings.db_path)
    try:
        rows = run_latent_entry_backtest(
            db,
            settings,
            horizons=[24],
            out_csv=settings.latent_backtest_csv_path,
            confirmation_hours=24,
            max_pre_signal_drift=0.05,
            min_cumulative_notional=1000,
            min_wallet_strength=60,
        )
    finally:
        db.close()

    assert len(rows) == 1
    row = rows[0]
    assert row["condition_id"] == "cond-3"
    assert row["wallet_address"] == "0xlatent"
    assert row["signal_ts"] == "2026-04-11 00:30:00"
    assert row["pre_signal_outcome_move"] == 0.02
    assert row["buy_trade_count_window"] == 2
    assert row["cumulative_buy_notional_window"] == 2700.0
    assert row["wallet_visible_in_holders"] is True
    assert row["fwd_24h_outcome_return"] == 0.43
    assert settings.latent_backtest_csv_path.exists()


def test_read_service_alerts_accept_structured_reasons_json(tmp_path: Path) -> None:
    settings = _build_fixture_db(tmp_path)
    from app.read_db import read_connection

    with read_connection(settings.db_path) as conn:
        alerts = list_alerts(conn, limit=10)

    assert alerts.total == 1
    assert alerts.items[0].reasons == ["price anomaly", "wallet quality"]


def test_read_service_recommendations_include_settled_feedback(tmp_path: Path) -> None:
    settings = _build_fixture_db(tmp_path)
    db = Database(settings.db_path)
    try:
        db.conn.execute(
            """
            INSERT INTO market_snapshots (
                condition_id, snapshot_ts, yes_price, no_price, yes_side, no_side, yes_holder_count, no_holder_count,
                yes_top_holder_amount, no_top_holder_amount, yes_top5_seen_share, no_top5_seen_share, observed_holder_wallets, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("cond-2", "2026-04-08 02:00:00", 1.0, 0.0, "buy", "sell", 10, 6, 300, 20, 0.82, 0.18, 18, "{}"),
        )
        db.conn.execute(
            """
            INSERT INTO alerts (
                alert_ts, condition_id, alert_type, score, score_total, score_price_anomaly,
                score_holder_concentration, score_wallet_quality, score_trade_flow, market_title,
                market_url, yes_token_id, current_yes_price, price_delta_6h, price_delta_24h,
                price_delta_72h, severity, confidence, action_label, reason_summary, summary, reasons_json, sent
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-04-07 20:00:00",
                "cond-2",
                "smart_money",
                9.1,
                9.1,
                3.0,
                2.0,
                2.1,
                2.0,
                "Closed Fixture Market",
                "https://polymarket.com/event/event-slug",
                "yes-token-2",
                0.62,
                0.11,
                0.19,
                None,
                "high",
                "high",
                "Monitor",
                "strong wallets accumulated before resolution",
                "Closed fixture summary",
                '{"reasons":["strong wallets accumulated before resolution"]}',
                0,
            ),
        )
        db.commit()
    finally:
        db.close()

    from app.read_db import read_connection

    with read_connection(settings.db_path) as conn:
        recommendations = list_recommendations(conn, limit=10)

    assert recommendations.total == 2
    assert recommendations.actionable == 1
    assert recommendations.settled == 1
    open_item = next(item for item in recommendations.items if item.condition_id == "cond-1")
    settled_item = next(item for item in recommendations.items if item.condition_id == "cond-2")
    assert open_item.recommendation == "consider_yes"
    assert open_item.status == "actionable"
    assert settled_item.status == "settled"
    assert settled_item.final_yes_price == 1.0
    assert settled_item.outcome_verdict == "good_call"
    assert settled_item.outcome_return == 0.6129


def test_api_serializes_overview_and_market_detail(tmp_path: Path, monkeypatch) -> None:
    settings = _build_fixture_db(tmp_path)
    monkeypatch.setattr("app.api_server.settings", settings)

    client = TestClient(app)
    overview_response = client.get("/api/v1/overview")
    detail_response = client.get("/api/v1/markets/cond-1")

    assert overview_response.status_code == 200
    assert overview_response.json()["watchlist_candidates"] == 1
    assert detail_response.status_code == 200
    assert detail_response.json()["condition_id"] == "cond-1"
    assert detail_response.json()["history_ready_6h"] is True
    assert detail_response.json()["market_url"] == "https://polymarket.com/event/event-slug"
    assert detail_response.json()["reward_asset_address"] == "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"


def test_api_market_trade_aftermath_endpoint(tmp_path: Path, monkeypatch) -> None:
    settings = _build_fixture_db(tmp_path)
    monkeypatch.setattr("app.api_server.settings", settings)

    client = TestClient(app)
    response = client.get("/api/v1/markets/cond-1/trade-aftermath?min_notional=1000&side=buy&outcome=Yes")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["trade_key"] == "trade-big-buy"
    assert payload["items"][0]["entry_snapshot_ts"] == "2026-04-09 00:00:00"
    assert payload["items"][0]["horizons"][1]["snapshot_ts"] == "2026-04-10 01:00:00"
    assert payload["items"][0]["surrounding_points"][0]["snapshot_ts"] == "2026-04-09 00:00:00"


def test_api_latent_backtests_endpoint_reads_generated_csv(tmp_path: Path, monkeypatch) -> None:
    settings = _build_fixture_db(tmp_path)
    db = Database(settings.db_path)
    try:
        run_latent_entry_backtest(
            db,
            settings,
            horizons=[24],
            out_csv=settings.latent_backtest_csv_path,
            confirmation_hours=24,
            max_pre_signal_drift=0.05,
            min_cumulative_notional=1000,
            min_wallet_strength=60,
        )
    finally:
        db.close()
    monkeypatch.setattr("app.api_server.settings", settings)

    client = TestClient(app)
    response = client.get("/api/v1/research/latent-backtests")

    assert response.status_code == 200
    payload = response.json()
    assert payload["exists"] is True
    assert payload["total_rows"] == 1
    assert payload["horizons"] == [24]


def test_api_alerts_endpoint_handles_structured_reasons_json(tmp_path: Path, monkeypatch) -> None:
    settings = _build_fixture_db(tmp_path)
    monkeypatch.setattr("app.api_server.settings", settings)

    client = TestClient(app)
    response = client.get("/api/v1/alerts")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["reasons"] == ["price anomaly", "wallet quality"]


def test_api_recommendations_endpoint_returns_open_and_settled_items(tmp_path: Path, monkeypatch) -> None:
    settings = _build_fixture_db(tmp_path)
    db = Database(settings.db_path)
    try:
        db.conn.execute(
            """
            INSERT INTO market_snapshots (
                condition_id, snapshot_ts, yes_price, no_price, yes_side, no_side, yes_holder_count, no_holder_count,
                yes_top_holder_amount, no_top_holder_amount, yes_top5_seen_share, no_top5_seen_share, observed_holder_wallets, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("cond-2", "2026-04-08 02:00:00", 0.0, 1.0, "buy", "sell", 9, 11, 40, 250, 0.24, 0.76, 19, "{}"),
        )
        db.conn.execute(
            """
            INSERT INTO alerts (
                alert_ts, condition_id, alert_type, score, score_total, score_price_anomaly,
                score_holder_concentration, score_wallet_quality, score_trade_flow, market_title,
                market_url, yes_token_id, current_yes_price, price_delta_6h, price_delta_24h,
                price_delta_72h, severity, confidence, action_label, reason_summary, summary, reasons_json, sent
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-04-07 20:00:00",
                "cond-2",
                "smart_money",
                7.5,
                7.5,
                3.0,
                1.5,
                1.5,
                1.5,
                "Closed Fixture Market",
                "https://polymarket.com/event/event-slug",
                "yes-token-2",
                0.61,
                0.1,
                0.16,
                None,
                "high",
                "medium",
                "Monitor",
                "pre-resolution flow looked one-sided",
                "Closed fixture summary",
                '{"reasons":["pre-resolution flow looked one-sided"]}',
                0,
            ),
        )
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr("app.api_server.settings", settings)

    client = TestClient(app)
    response = client.get("/api/v1/recommendations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["actionable"] == 1
    assert payload["settled"] == 1
    settled_item = next(item for item in payload["items"] if item["condition_id"] == "cond-2")
    assert settled_item["status"] == "settled"
    assert settled_item["outcome_verdict"] == "bad_call"
    assert settled_item["final_yes_price"] == 0.0


def test_api_system_action_runs_latent_backtest(tmp_path: Path, monkeypatch) -> None:
    settings = _build_fixture_db(tmp_path)
    monkeypatch.setattr("app.api_server.settings", settings)

    client = TestClient(app)
    response = client.post(
        "/api/v1/system/actions/run",
        json={
            "action": "latent-backtest",
            "hours": [24],
            "confirm_hours": 24,
            "max_drift": 0.05,
            "min_notional": 1000,
            "min_wallet_score": 60,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_name"] == "latent-backtest"
    assert payload["rows_written"] == 1
    assert Path(payload["output_path"]).name == "latent_backtest.csv"


def test_api_markets_filters_and_sorting(tmp_path: Path, monkeypatch) -> None:
    settings = _build_fixture_db(tmp_path)
    monkeypatch.setattr("app.api_server.settings", settings)

    client = TestClient(app)
    closed_response = client.get("/api/v1/markets?status=closed&sort=end_date_desc")
    open_response = client.get("/api/v1/markets?status=open")

    assert closed_response.status_code == 200
    assert closed_response.json()["total"] == 2
    assert closed_response.json()["items"][0]["condition_id"] == "cond-3"
    assert closed_response.json()["items"][0]["closed"] is True

    assert open_response.status_code == 200
    assert open_response.json()["total"] == 1
    assert open_response.json()["items"][0]["condition_id"] == "cond-1"
    assert open_response.json()["items"][0]["accepting_orders"] is True
