"""FastAPI HTTP server — serves TitanTrade state files as JSON endpoints.

Run with:
    uv run uvicorn titantrade.api:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import json
import logging
import threading
import traceback
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

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


app = FastAPI(title="TitanTrade API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "PUT", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_state(filename: str) -> dict:
    """Read a JSON file from state/. Returns empty dict if missing."""
    path = STATE_DIR / filename
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _read_data(filename: str) -> dict:
    """Read a JSON file from data/. Returns empty dict if missing."""
    path = DATA_DIR / filename
    if not path.exists():
        return {}
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# State endpoints (read-only)
# ---------------------------------------------------------------------------

@app.get("/api/portfolio")
def portfolio() -> dict:
    """Return live portfolio data from Alpaca (account + positions)."""
    try:
        from .config import load_config
        from .executor import get_account, get_positions

        cfg = load_config()
        account = get_account(cfg)
        positions = get_positions(cfg)
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
                for p in positions
            ],
        }
    except Exception as exc:
        log.error(f"Failed to fetch live portfolio: {exc}")
        # Fall back to static file
        data = _read_state("portfolio.json")
        if not data:
            raise HTTPException(status_code=503, detail=f"Portfolio unavailable: {exc}")
        return data


@app.get("/api/trades")
def trades() -> dict:
    data = _read_state("trade_log.json")
    return data if data else {"trades": []}


@app.get("/api/theses")
def theses() -> dict:
    data = _read_state("weekly_thesis.json")
    if not data:
        raise HTTPException(status_code=404, detail="weekly_thesis.json not found")
    return data


@app.get("/api/sentry")
def sentry() -> dict:
    data = _read_state("sentry_signals.json")
    if not data:
        raise HTTPException(status_code=404, detail="sentry_signals.json not found")
    return data


@app.get("/api/near-misses")
def near_misses() -> dict:
    data = _read_state("near_misses.json")
    return data if data else {"near_misses": []}


@app.get("/api/costs")
def costs() -> dict:
    data = _read_state("costs.json")
    return data if data else {"costs": []}


@app.get("/api/trailing-stops")
def trailing_stops() -> dict:
    return _read_state("trailing_stops.json")


@app.get("/api/pricecheck")
def pricecheck() -> dict:
    return _read_state("pricecheck_signals.json")


# ---------------------------------------------------------------------------
# Settings (trading mode)
# ---------------------------------------------------------------------------

@app.get("/api/settings")
def get_settings() -> dict:
    """Return current trading settings and whether live keys are configured."""
    data = _read_data("watchlist.json")
    settings = data.get("settings", {})
    return {
        "trading_mode": settings.get("trading_mode", "paper"),
        "live_keys_configured": live_keys_configured(),
    }


class TradingModeUpdate(BaseModel):
    trading_mode: str


@app.put("/api/settings/mode")
def put_trading_mode(body: TradingModeUpdate) -> dict:
    """Switch between paper and live trading mode."""
    if body.trading_mode not in ("paper", "live"):
        raise HTTPException(status_code=400, detail="trading_mode must be 'paper' or 'live'")
    if body.trading_mode == "live" and not live_keys_configured():
        raise HTTPException(
            status_code=400,
            detail="Cannot enable live trading: ALPACA_LIVE_KEY and ALPACA_LIVE_SECRET not configured",
        )
    save_trading_mode(body.trading_mode)
    return {"trading_mode": body.trading_mode}


# ---------------------------------------------------------------------------
# Watchlist (read + write)
# ---------------------------------------------------------------------------

@app.get("/api/watchlist")
def get_watchlist() -> dict:
    return _read_data("watchlist.json")


class WatchlistUpdate(BaseModel):
    watchlist: list[str]


@app.put("/api/watchlist")
def put_watchlist(body: WatchlistUpdate) -> dict:
    save_watchlist(body.watchlist)
    return _read_data("watchlist.json")


# ---------------------------------------------------------------------------
# Action endpoints — trigger long-running tasks
# ---------------------------------------------------------------------------

# In-memory job tracking (simple, server-lifetime only)
_jobs: dict[str, dict[str, Any]] = {}


def _run_in_thread(job_id: str, fn, *args, **kwargs) -> None:
    """Run a function in a background thread, tracking status in _jobs."""
    _jobs[job_id]["status"] = "running"
    _jobs[job_id]["started_at"] = datetime.now(timezone.utc).isoformat()
    try:
        result = fn(*args, **kwargs)
        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["result"] = result
    except Exception as exc:
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(exc)
        _jobs[job_id]["traceback"] = traceback.format_exc()
    _jobs[job_id]["finished_at"] = datetime.now(timezone.utc).isoformat()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    """Check status of a background job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/api/actions/analyze")
def trigger_analysis() -> dict:
    """Trigger the full weekly analysis pipeline (fetch + analyze). Runs in background."""
    job_id = f"analyze_{uuid.uuid4().hex[:8]}"
    _jobs[job_id] = {"id": job_id, "action": "analyze", "status": "queued"}

    def _run():
        from .config import load_config
        from .weekly_analyst import run_weekly_analysis
        cfg = load_config()
        result = run_weekly_analysis(cfg)
        theses = result.get("theses", [])
        selected = [t["ticker"] for t in theses if t.get("selected_for_trading")]
        return {
            "theses_count": len(theses),
            "selected": selected,
            "regime": result.get("market_regime", "unknown"),
        }

    threading.Thread(target=_run_in_thread, args=(job_id, _run), daemon=True).start()
    return {"job_id": job_id, "status": "queued"}


@app.post("/api/actions/download-history")
def trigger_download_history() -> dict:
    """Download historical OHLCV data for backtesting. Runs in background."""
    job_id = f"download_{uuid.uuid4().hex[:8]}"
    _jobs[job_id] = {"id": job_id, "action": "download-history", "status": "queued"}

    def _run():
        from .config import load_config
        from .backtest.data_loader import download_historical_data
        cfg = load_config()
        data_dir = str(DATA_DIR / "historical")
        download_historical_data(cfg.trading.watchlist, cfg, data_dir)
        return {"data_dir": data_dir, "tickers": cfg.trading.watchlist}

    threading.Thread(target=_run_in_thread, args=(job_id, _run), daemon=True).start()
    return {"job_id": job_id, "status": "queued"}


@app.post("/api/actions/backtest")
def trigger_backtest() -> dict:
    """Run backtest on downloaded historical data. Runs in background."""
    job_id = f"backtest_{uuid.uuid4().hex[:8]}"
    _jobs[job_id] = {"id": job_id, "action": "backtest", "status": "queued"}

    def _run():
        from .config import load_config
        from .backtest.engine import run_backtest
        cfg = load_config()
        data_dir = str(DATA_DIR / "historical")
        result = run_backtest(data_dir=data_dir, tickers=cfg.trading.watchlist)
        # Save results to state for the app to display
        results_path = STATE_DIR / "backtest_results.json"
        with open(results_path, "w") as f:
            json.dump(result, f, indent=2)
        return result

    threading.Thread(target=_run_in_thread, args=(job_id, _run), daemon=True).start()
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/backtest-results")
def backtest_results() -> dict:
    """Get the latest backtest results."""
    data = _read_state("backtest_results.json")
    if not data:
        raise HTTPException(status_code=404, detail="No backtest results yet")
    return data


# ---------------------------------------------------------------------------
# Scheduler endpoints
# ---------------------------------------------------------------------------

@app.get("/api/scheduler")
def scheduler_status() -> dict:
    """List all scheduled jobs with next_run and last_run info."""
    return {"jobs": get_all_jobs()}


@app.get("/api/scheduler/{job_id}")
def scheduler_job_detail(job_id: str) -> dict:
    """Get run history for a specific scheduled job."""
    return {"job_id": job_id, "history": get_job_history(job_id)}


@app.post("/api/scheduler/{job_id}/trigger")
def scheduler_trigger(job_id: str) -> dict:
    """Manually trigger a scheduled job to run immediately."""
    if not trigger_job(job_id):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {"job_id": job_id, "status": "triggered"}


class JobEnabledUpdate(BaseModel):
    enabled: bool


@app.put("/api/scheduler/{job_id}/enabled")
def scheduler_set_enabled(job_id: str, body: JobEnabledUpdate) -> dict:
    """Enable or disable a scheduled job."""
    if not set_job_enabled(job_id, body.enabled):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {"job_id": job_id, "enabled": body.enabled}
