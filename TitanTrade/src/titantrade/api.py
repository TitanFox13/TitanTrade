"""FastAPI HTTP server — hosts the scheduler and serves the state files.

Run with:
    uv run uvicorn titantrade.api:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import DATA_DIR, STATE_DIR, live_keys_configured, save_trading_mode, save_watchlist
from .scheduler import (
    get_all_jobs,
    get_job_history,
    set_job_enabled,
    start_scheduler,
    stop_scheduler,
    trigger_job,
)

log = logging.getLogger("titantrade.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="TitanTrade API", version="3.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "PUT", "POST"], allow_headers=["*"],
)


def _read_state(filename: str) -> dict:
    """A JSON file from state/, or {} when missing."""
    path = STATE_DIR / filename
    return json.loads(path.read_text()) if path.exists() else {}


def _read_data(filename: str) -> dict:
    path = DATA_DIR / filename
    return json.loads(path.read_text()) if path.exists() else {}


def _state_or_404(filename: str) -> dict:
    data = _read_state(filename)
    if not data:
        raise HTTPException(status_code=404, detail=f"{filename} not found")
    return data


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# --- Book & strategy state -----------------------------------------------------

@app.get("/api/portfolio")
def portfolio() -> dict:
    """Live account + positions from Alpaca (falls back to state/portfolio.json)."""
    try:
        from .broker import get_account, get_positions
        from .config import load_config

        cfg = load_config()
        account = get_account(cfg)
        return {
            "portfolio_value": float(account.get("portfolio_value", 0)),
            "cash": float(account.get("cash", 0)),
            "buying_power": float(account.get("buying_power", 0)),
            "equity": float(account.get("equity", 0)),
            "positions": [
                {
                    "ticker": p.get("symbol", ""),
                    "qty": float(p.get("qty", 0)),
                    "market_value": float(p.get("market_value", 0)),
                    "avg_entry_price": float(p.get("avg_entry_price", 0)),
                    "current_price": float(p.get("current_price", 0)),
                    "unrealized_pl": float(p.get("unrealized_pl", 0)),
                    "unrealized_plpc": float(p.get("unrealized_plpc", 0)),
                    "side": p.get("side", ""),
                }
                for p in get_positions(cfg)
            ],
        }
    except Exception as exc:  # noqa: BLE001
        log.error(f"Failed to fetch live portfolio: {exc}")
        data = _read_state("portfolio.json")
        if not data:
            raise HTTPException(status_code=503, detail=f"Portfolio unavailable: {exc}")
        return data


@app.get("/api/plan")
def plan() -> dict:
    """The current plan: NEW/HOLD items, watch list, insurance state, slots."""
    return _state_or_404("plan.json")


@app.get("/api/trades")
def trades() -> dict:
    return _read_state("trade_log.json") or {"trades": []}


@app.get("/api/near-misses")
def near_misses() -> dict:
    return _read_state("near_misses.json") or {"near_misses": []}


@app.get("/api/costs")
def costs() -> dict:
    return _read_state("costs.json") or {"costs": []}


@app.get("/api/universe-proposal")
def universe_proposal() -> dict:
    """The monthly LLM universe-curation proposal (advisory)."""
    return _state_or_404("universe_proposal.json")


@app.get("/api/post-mortem")
def post_mortem() -> dict:
    return _state_or_404("post_mortem.json")


@app.get("/api/fill-ledger")
def fill_ledger() -> dict:
    """Fill vs the backtest's price per entry (Decision 069) with the median gap."""
    from .fill_ledger import load_ledger, summary

    rows = load_ledger().get("rows", [])
    return {"summary": summary(rows), "rows": rows}


# --- Benchmark -----------------------------------------------------------------

@app.get("/api/benchmark")
def benchmark() -> dict:
    """Last-computed metrics vs SPY (refreshed by the daily summary)."""
    return _read_state("benchmark_metrics.json") or {
        "insufficient_data": True,
        "note": "Not yet computed — runs with the daily summary, or GET /api/benchmark/refresh.",
    }


@app.get("/api/benchmark/refresh")
def benchmark_refresh(days: int = 90, since: str | None = None) -> dict:
    try:
        from .benchmark import compute_benchmark
        from .config import load_config

        return compute_benchmark(load_config(), lookback_days=days, since=since)
    except Exception as exc:  # noqa: BLE001
        log.error(f"Benchmark refresh failed: {exc}")
        raise HTTPException(status_code=503, detail=f"Benchmark unavailable: {exc}")


# --- Settings & watchlist ------------------------------------------------------

@app.get("/api/settings")
def get_settings() -> dict:
    settings = _read_data("watchlist.json").get("settings", {})
    return {
        "trading_mode": settings.get("trading_mode", "paper"),
        "mechanical": settings.get("mechanical", {}),
        "live_keys_configured": live_keys_configured(),
    }


class TradingModeUpdate(BaseModel):
    trading_mode: str


@app.put("/api/settings/mode")
def put_trading_mode(body: TradingModeUpdate) -> dict:
    if body.trading_mode not in ("paper", "live"):
        raise HTTPException(status_code=400, detail="trading_mode must be 'paper' or 'live'")
    if body.trading_mode == "live" and not live_keys_configured():
        raise HTTPException(
            status_code=400,
            detail="Cannot enable live trading: ALPACA_LIVE_KEY and ALPACA_LIVE_SECRET not configured",
        )
    save_trading_mode(body.trading_mode)
    return {"trading_mode": body.trading_mode}


@app.get("/api/watchlist")
def get_watchlist() -> dict:
    return _read_data("watchlist.json")


class WatchlistUpdate(BaseModel):
    watchlist: list[str]


@app.put("/api/watchlist")
def put_watchlist(body: WatchlistUpdate) -> dict:
    save_watchlist(body.watchlist)
    return _read_data("watchlist.json")


# --- Scheduler -----------------------------------------------------------------

@app.get("/api/scheduler")
def scheduler_status() -> dict:
    return {"jobs": get_all_jobs()}


@app.get("/api/scheduler/{job_id}")
def scheduler_job_detail(job_id: str) -> dict:
    return {"job_id": job_id, "history": get_job_history(job_id)}


@app.post("/api/scheduler/{job_id}/trigger")
def scheduler_trigger(job_id: str) -> dict:
    if not trigger_job(job_id):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {"job_id": job_id, "status": "triggered"}


class JobEnabledUpdate(BaseModel):
    enabled: bool


@app.put("/api/scheduler/{job_id}/enabled")
def scheduler_set_enabled(job_id: str, body: JobEnabledUpdate) -> dict:
    if not set_job_enabled(job_id, body.enabled):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {"job_id": job_id, "enabled": body.enabled}
