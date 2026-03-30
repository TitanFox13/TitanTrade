"""Load historical data for backtesting.

download_historical_data(): One-time FMP download — run BEFORE backtesting.
load_historical_data(): Load from saved files — used DURING backtesting.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def download_historical_data(
    tickers: list[str],
    fmp_key: str,
    output_dir: str,
    days: int = 750,
) -> None:
    """Download OHLCV from FMP and save as JSON. Run once before backtesting.

    This is the ONLY function in the backtest package that makes API calls.
    """
    from titantrade.retry import fetch_with_retry

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    today = datetime.now(timezone.utc).date()
    from_date = today - timedelta(days=int(days * 1.5))

    for ticker in tickers + ["SPY"]:
        url = "https://financialmodelingprep.com/stable/historical-price-eod/full"
        params = {
            "symbol": ticker,
            "from": from_date.isoformat(),
            "to": today.isoformat(),
            "apikey": fmp_key,
        }

        print(f"Downloading {ticker}...")
        resp = fetch_with_retry("GET", url, params=params)
        data = resp.json()

        historical = data.get("historical", [])
        bars = [
            {
                "date": bar["date"],
                "open": bar["open"],
                "high": bar["high"],
                "low": bar["low"],
                "close": bar["close"],
                "volume": bar["volume"],
            }
            for bar in reversed(historical)
        ]

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
