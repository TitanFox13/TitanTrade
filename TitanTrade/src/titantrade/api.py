"""FastAPI HTTP server — serves TitanTrade state files as JSON endpoints.

Run with:
    uv run uvicorn titantrade.api:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import DATA_DIR, STATE_DIR, save_watchlist

app = FastAPI(title="TitanTrade API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "PUT"],
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
