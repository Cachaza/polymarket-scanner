from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .backtest import run_backtest
from .config import get_settings
from .db import Database
from .diagnostics import render_diagnostics
from .jobs import discover, refresh_leaderboard, score_alerts, snapshot
from .logger import configure_logging


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
    bt.add_argument("--out", type=Path, default=Path("data/backtest.csv"))
    return parser


def main() -> None:
    configure_logging(logging.INFO)
    settings = get_settings()
    parser = build_parser()
    args = parser.parse_args()

    db = Database(settings.db_path)
    try:
        schema_path = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"
        db.init_schema(schema_path)
        if args.command == "init-db":
            print(f"Initialized DB at {settings.db_path}")
            return

        if args.command == "discover":
            discover.run(settings, db)
        elif args.command == "diagnostics":
            print(render_diagnostics(settings, db))
        elif args.command == "refresh-leaderboard":
            refresh_leaderboard.run(settings, db)
        elif args.command == "snapshot":
            snapshot.run(settings, db)
        elif args.command == "score-alerts":
            score_alerts.run(settings, db)
        elif args.command == "run-cycle":
            discover.run(settings, db)
            refresh_leaderboard.run(settings, db)
            snapshot.run(settings, db)
            score_alerts.run(settings, db)
        elif args.command == "backtest":
            results = run_backtest(db, settings, horizons=args.hours, out_csv=args.out)
            print(f"Backtest rows: {len(results)}")
            print(f"Wrote: {args.out}")
        else:
            parser.error(f"Unknown command: {args.command}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
