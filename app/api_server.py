from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .api_models import (
    AlertsResponse,
    BacktestResponse,
    HoldersResponse,
    JobActionRequest,
    JobActionResponse,
    MarketDetailResponse,
    MarketsResponse,
    OverviewResponse,
    RecommendationsResponse,
    SystemResponse,
    TradeAftermathResponse,
    TimeSeriesResponse,
    TradesResponse,
    WatchlistResponse,
)
from .backtest import run_backtest, run_latent_entry_backtest
from .config import get_settings
from .db import Database
from .job_runs import tracked_job
from .jobs import discover, refresh_leaderboard, score_alerts, snapshot
from .read_db import read_connection
from .read_service import (
    get_backtests,
    get_latent_backtests,
    get_market_detail,
    get_market_holders,
    get_market_trade_aftermath,
    get_market_timeseries,
    get_market_trades,
    get_overview,
    list_recommendations,
    get_system,
    get_watchlist,
    list_alerts,
    list_markets,
)
from .schema import get_schema_path

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Apply schema migrations on every startup (idempotent)."""
    if not settings.database_url:
        raise RuntimeError(
            "POLY_DATABASE_URL is not set. "
            "Set it in Dokploy environment variables and redeploy."
        )
    logger.info("Applying database schema to %s...", settings.database_url.split("@")[-1])
    db = Database(settings.database_url)
    try:
        db.init_schema(get_schema_path())
        db.commit()
        logger.info("Schema applied successfully.")
    except Exception as exc:
        logger.exception("Failed to apply schema on startup: %s", exc)
        raise
    finally:
        db.close()
    yield



app = FastAPI(title="Polymarket Scanner API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _rows_written(result: object) -> int | None:
    if isinstance(result, list):
        return len(result)
    if not isinstance(result, dict):
        return None
    for key in ("markets", "wallet_score_rows", "new_alerts", "watchlist_candidates", "recommendations", "events"):
        value = result.get(key)
        if isinstance(value, int):
            return value
    return None


def _run_job_action(request: JobActionRequest) -> JobActionResponse:
    action = request.action
    db = Database(settings.database_url)
    try:
        db.init_schema(get_schema_path())
        if action == "discover":
            runner = lambda: discover.run(settings, db)
            output_path: Path | None = None
        elif action == "refresh-leaderboard":
            runner = lambda: refresh_leaderboard.run(settings, db)
            output_path = None
        elif action == "snapshot":
            runner = lambda: snapshot.run(settings, db)
            output_path = None
        elif action == "score-alerts":
            runner = lambda: score_alerts.run(settings, db)
            output_path = None
        elif action == "backtest":
            output_path = settings.backtest_csv_path
            runner = lambda: run_backtest(db, settings, horizons=request.hours, out_csv=output_path)
        elif action == "latent-backtest":
            output_path = settings.latent_backtest_csv_path
            runner = lambda: run_latent_entry_backtest(
                db,
                settings,
                horizons=request.hours,
                out_csv=output_path,
                confirmation_hours=request.confirm_hours or 24,
                max_pre_signal_drift=request.max_drift if request.max_drift is not None else 0.05,
                min_cumulative_notional=request.min_notional if request.min_notional is not None else 1000.0,
                min_wallet_strength=request.min_wallet_score if request.min_wallet_score is not None else 60.0,
            )
        elif action == "run-cycle":
            def cycle_runner():
                discover.run(settings, db)
                refresh_leaderboard.run(settings, db)
                snapshot.run(settings, db)
                return score_alerts.run(settings, db)

            runner = cycle_runner
            output_path = None
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported action: {action}")

        with tracked_job(db, action) as state:
            result = runner()
            state["rows_written"] = _rows_written(result)
            if isinstance(result, dict):
                state["meta"] = result
            elif isinstance(result, list):
                state["meta"] = {"rows": len(result)}

        return JobActionResponse(
            job_name=action,
            status="completed",
            rows_written=_rows_written(result),
            meta=state.get("meta", {}),
            output_path=str(output_path) if output_path is not None else None,
        )
    finally:
        db.close()


@app.get("/api/v1/overview", response_model=OverviewResponse)
def overview() -> OverviewResponse:
    with read_connection(settings.database_url) as conn:
        return get_overview(conn, settings)


@app.get("/api/v1/markets", response_model=MarketsResponse)
def markets(
    search: str | None = None,
    status: str = Query(default="open", pattern="^(open|closed|archived|all)$"),
    history: str | None = Query(default=None, pattern="^(6h|24h|72h)?$"),
    watchlist_only: bool = False,
    sort: str = "watchlist_desc",
    limit: int = Query(default=50, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
) -> MarketsResponse:
    with read_connection(settings.database_url) as conn:
        return list_markets(
            conn,
            settings,
            search=search,
            status=status,
            history=history,
            watchlist_only=watchlist_only,
            sort=sort,
            limit=limit,
            offset=offset,
        )


@app.get("/api/v1/watchlist", response_model=WatchlistResponse)
def watchlist(
    warmup_only: bool | None = None,
    limit: int = Query(default=100, ge=1, le=250),
) -> WatchlistResponse:
    with read_connection(settings.database_url) as conn:
        return get_watchlist(conn, warmup_only=warmup_only, limit=limit)


@app.get("/api/v1/alerts", response_model=AlertsResponse)
def alerts(
    severity: str | None = None,
    confidence: str | None = None,
    alert_type: str | None = None,
    condition_id: str | None = None,
    hours: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
) -> AlertsResponse:
    with read_connection(settings.database_url) as conn:
        return list_alerts(
            conn,
            severity=severity,
            confidence=confidence,
            alert_type=alert_type,
            condition_id=condition_id,
            hours=hours,
            limit=limit,
            offset=offset,
        )


@app.get("/api/v1/recommendations", response_model=RecommendationsResponse)
def recommendations(limit: int = Query(default=100, ge=1, le=250)) -> RecommendationsResponse:
    with read_connection(settings.database_url) as conn:
        return list_recommendations(conn, limit=limit)


@app.get("/api/v1/markets/{condition_id}", response_model=MarketDetailResponse)
def market_detail(condition_id: str) -> MarketDetailResponse:
    with read_connection(settings.database_url) as conn:
        detail = get_market_detail(conn, condition_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Market not found")
    return detail


@app.get("/api/v1/markets/{condition_id}/timeseries", response_model=TimeSeriesResponse)
def market_timeseries(condition_id: str, hours: int = Query(default=168, ge=1, le=24 * 30)) -> TimeSeriesResponse:
    with read_connection(settings.database_url) as conn:
        return get_market_timeseries(conn, condition_id, hours)


@app.get("/api/v1/markets/{condition_id}/holders", response_model=HoldersResponse)
def market_holders(condition_id: str, snapshot: str = "latest") -> HoldersResponse:
    with read_connection(settings.database_url) as conn:
        return get_market_holders(conn, condition_id, snapshot)


@app.get("/api/v1/markets/{condition_id}/trades", response_model=TradesResponse)
def market_trades(condition_id: str, limit: int = Query(default=50, ge=1, le=100)) -> TradesResponse:
    with read_connection(settings.database_url) as conn:
        return get_market_trades(conn, condition_id, limit)


@app.get("/api/v1/markets/{condition_id}/trade-aftermath", response_model=TradeAftermathResponse)
def market_trade_aftermath(
    condition_id: str,
    limit: int = Query(default=8, ge=1, le=25),
    min_notional: float | None = Query(default=1000, ge=0),
    side: str = Query(default="buy", pattern="^(buy|sell|all)$"),
    outcome: str = Query(default="all", pattern="^(Yes|No|all)$"),
) -> TradeAftermathResponse:
    with read_connection(settings.database_url) as conn:
        return get_market_trade_aftermath(
            conn,
            condition_id,
            limit=limit,
            min_notional=min_notional,
            side=side,
            outcome=outcome,
        )


@app.get("/api/v1/research/backtests", response_model=BacktestResponse)
def backtests() -> BacktestResponse:
    return get_backtests(settings)


@app.get("/api/v1/research/latent-backtests", response_model=BacktestResponse)
def latent_backtests() -> BacktestResponse:
    return get_latent_backtests(settings)


@app.post("/api/v1/system/actions/run", response_model=JobActionResponse)
def run_system_action(request: JobActionRequest) -> JobActionResponse:
    return _run_job_action(request)


@app.get("/api/v1/system", response_model=SystemResponse)
def system() -> SystemResponse:
    with read_connection(settings.database_url) as conn:
        return get_system(conn, settings)


def main() -> None:
    host = os.getenv("POLY_API_HOST", "127.0.0.1")
    port = int(os.getenv("POLY_API_PORT", "8000"))
    uvicorn.run("app.api_server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
