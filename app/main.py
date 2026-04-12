from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .backtest import run_backtest, run_latent_entry_backtest
from .config import get_settings
from .db import Database
from .diagnostics import render_diagnostics
from .job_runs import tracked_job
from .jobs import discover, refresh_leaderboard, score_alerts, snapshot
from .logger import configure_logging
from .schema import get_schema_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Polymarket anomaly scanner")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db")
    sub.add_parser("discover")
    sub.add_parser("diagnostics")
    sub.add_parser("refresh-leaderboard")
    sub.add_parser("snapshot")
    sub.add_parser("score-alerts")
    sub.add_parser("run-cycle")

    bt = sub.add_parser("backtest")
    bt.add_argument("--hours", type=int, nargs="+", default=[6, 24, 72])
    bt.add_argument("--out", type=Path)

    latent_bt = sub.add_parser("latent-backtest")
    latent_bt.add_argument("--hours", type=int, nargs="+", default=[24, 72, 120])
    latent_bt.add_argument("--out", type=Path)
    latent_bt.add_argument("--confirm-hours", type=int, default=24)
    latent_bt.add_argument("--max-drift", type=float, default=0.05)
    latent_bt.add_argument("--min-notional", type=float, default=1000.0)
    latent_bt.add_argument("--min-wallet-score", type=float, default=60.0)
    return parser


def _rows_written_for(job_name: str, result: object) -> int | None:
    if job_name in {"backtest", "latent-backtest"} and isinstance(result, list):
        return len(result)
    if not isinstance(result, dict):
        return None
    for key in ("markets", "wallet_score_rows", "new_alerts", "watchlist_candidates", "events"):
        value = result.get(key)
        if isinstance(value, int):
            return value
    return None


def _run_tracked_job(db: Database, job_name: str, runner) -> object:
    with tracked_job(db, job_name) as state:
        result = runner()
        state["rows_written"] = _rows_written_for(job_name, result)
        if isinstance(result, dict):
            state["meta"] = result
        return result


def main() -> None:
    configure_logging(logging.INFO)
    settings = get_settings()
    parser = build_parser()
    args = parser.parse_args()

    db = Database(settings.database_url)
    try:
        db.init_schema(get_schema_path())
        if args.command == "init-db":
            print(f"Initialized DB at {settings.database_url}")
            return

        if args.command == "discover":
            _run_tracked_job(db, "discover", lambda: discover.run(settings, db))
        elif args.command == "diagnostics":
            print(render_diagnostics(settings, db))
        elif args.command == "refresh-leaderboard":
            _run_tracked_job(db, "refresh-leaderboard", lambda: refresh_leaderboard.run(settings, db))
        elif args.command == "snapshot":
            _run_tracked_job(db, "snapshot", lambda: snapshot.run(settings, db))
        elif args.command == "score-alerts":
            _run_tracked_job(db, "score-alerts", lambda: score_alerts.run(settings, db))
        elif args.command == "run-cycle":
            _run_tracked_job(db, "discover", lambda: discover.run(settings, db))
            _run_tracked_job(db, "refresh-leaderboard", lambda: refresh_leaderboard.run(settings, db))
            _run_tracked_job(db, "snapshot", lambda: snapshot.run(settings, db))
            _run_tracked_job(db, "score-alerts", lambda: score_alerts.run(settings, db))
        elif args.command == "backtest":
            out_csv = args.out or settings.backtest_csv_path
            results = _run_tracked_job(
                db,
                "backtest",
                lambda: run_backtest(db, settings, horizons=args.hours, out_csv=out_csv),
            )
            print(f"Backtest rows: {len(results)}")
            print(f"Wrote: {out_csv}")
        elif args.command == "latent-backtest":
            out_csv = args.out or settings.latent_backtest_csv_path
            results = _run_tracked_job(
                db,
                "latent-backtest",
                lambda: run_latent_entry_backtest(
                    db,
                    settings,
                    horizons=args.hours,
                    out_csv=out_csv,
                    confirmation_hours=args.confirm_hours,
                    max_pre_signal_drift=args.max_drift,
                    min_cumulative_notional=args.min_notional,
                    min_wallet_strength=args.min_wallet_score,
                ),
            )
            print(f"Latent backtest rows: {len(results)}")
            print(f"Wrote: {out_csv}")
        else:
            parser.error(f"Unknown command: {args.command}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
