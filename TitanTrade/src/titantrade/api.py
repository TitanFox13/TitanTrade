"""FastAPI HTTP server — serves TitanTrade state files as JSON endpoints.

Run with:
    uv run uvicorn titantrade.api:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import json
import threading
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import DATA_DIR, STATE_DIR, save_watchlist

app = FastAPI(title="TitanTrade API", version="1.0.0")

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
    data = _read_state("portfolio.json")
    if not data:
        raise HTTPException(status_code=404, detail="portfolio.json not found")
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
        download_historical_data(cfg.trading.watchlist, cfg.fmp.key, data_dir)
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
