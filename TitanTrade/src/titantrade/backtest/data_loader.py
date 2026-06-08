"""Load historical data for backtesting.

download_historical_data(): One-time Alpaca download — run BEFORE backtesting.
load_historical_data(): Load from saved files — used DURING backtesting.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from titantrade.config import Config


def download_historical_data(
    tickers: list[str],
    cfg: Config,
    output_dir: str,
    days: int = 750,
) -> None:
    """Download OHLCV from Alpaca and save as JSON. Run once before backtesting.

    This is the ONLY function in the backtest package that makes API calls.
    """
    from titantrade import market_data

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    for ticker in tickers + ["SPY"]:
        print(f"Downloading {ticker}...")
        bars = market_data.get_ohlcv(ticker, cfg, days=days)
        path = out / f"{ticker}.json"
        with open(path, "w") as f:
            json.dump(bars, f)
        print(f"  Saved {len(bars)} bars to {path}")

    print(f"Download complete. Data saved to {output_dir}/")


def load_historical_data(
    tickers: list[str],
    data_dir: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Load saved OHLCV from JSON files. Zero API calls."""
    data_path = Path(data_dir)
    result: dict[str, list[dict[str, Any]]] = {}

    for ticker in tickers:
        path = data_path / f"{ticker}.json"
        if not path.exists():
            print(f"  Warning: no data file for {ticker} at {path}")
            continue

        with open(path) as f:
            bars = json.load(f)

        if start_date:
            bars = [b for b in bars if b["date"] >= start_date]
        if end_date:
            bars = [b for b in bars if b["date"] <= end_date]

        result[ticker] = bars

    return result
