"""Earnings calendar gate: block new entries within N days of earnings.

Earnings create binary risk that no analysis can predict. A stock can drop
10% overnight on a miss. This module provides a hard gate that the executor
enforces regardless of what the AI recommends.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from titantrade.config import Config
from titantrade.logger import get_logger
from titantrade.retry import fetch_with_retry

log = get_logger("earnings")

# Narrowed from 5 to 2 calendar days. The 5-day window blocked entries even
# when earnings were 3-4 trading days away, missing many setup opportunities.
# 2 days = report tonight or tomorrow morning, which is the actual binary-
# event risk window. Earlier moves get analyzed normally.
DEFAULT_BLOCK_DAYS = 2


def fetch_earnings_date(ticker: str, cfg: Config) -> str | None:
    """Fetch the next upcoming earnings date from FMP.

    Returns ISO date string (YYYY-MM-DD) or None if not found.
    """
    url = "https://financialmodelingprep.com/stable/earnings-calendar"
    today = datetime.now(timezone.utc).date()
    params = {
        "from": today.isoformat(),
        "to": (today + timedelta(days=60)).isoformat(),
        "apikey": cfg.fmp.key,
    }

    try:
        resp = fetch_with_retry("GET", url, params=params)
        data = resp.json()
    except Exception as exc:
        log.warning(f"Failed to fetch earnings calendar: {exc}")
        return None

    for entry in data:
        if entry.get("symbol") == ticker:
            return entry.get("date")

    return None


def fetch_all_earnings_dates(
    tickers: list[str], cfg: Config
) -> dict[str, str | None]:
    """Fetch upcoming earnings dates for all tickers in one pass.

    FMP returns the full calendar, so we only make one API call
    and filter for our watchlist.
    """
    url = "https://financialmodelingprep.com/stable/earnings-calendar"
    today = datetime.now(timezone.utc).date()
    params = {
        "from": today.isoformat(),
        "to": (today + timedelta(days=60)).isoformat(),
        "apikey": cfg.fmp.key,
    }

    try:
        resp = fetch_with_retry("GET", url, params=params)
        data = resp.json()
    except Exception as exc:
        log.warning(f"Failed to fetch earnings calendar: {exc}")
        return {t: None for t in tickers}

    ticker_set = set(tickers)
    result: dict[str, str | None] = {t: None for t in tickers}

    for entry in data:
        symbol = entry.get("symbol", "")
        if symbol in ticker_set and result[symbol] is None:
            result[symbol] = entry.get("date")

    return result


def is_earnings_blocked(
    ticker: str,
    earnings_date: str | None,
    block_days: int = DEFAULT_BLOCK_DAYS,
) -> tuple[bool, int | None]:
    """Check if a ticker is within the earnings blackout window.

    Returns (is_blocked, days_until_earnings).
    - is_blocked: True if earnings are within block_days trading days
    - days_until_earnings: calendar days until earnings (None if unknown)
    """
    if earnings_date is None:
        return False, None

    try:
        earnings_dt = datetime.strptime(earnings_date, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return False, None

    now = datetime.now(timezone.utc)
    delta = (earnings_dt - now).days

    if delta < 0:
        # Earnings already passed (stale data)
        return False, None

    # Block if within N calendar days (roughly maps to trading days)
    # Using calendar days is slightly conservative, which is what we want
    blocked = delta <= block_days
    if blocked:
        log.info(
            f"EARNINGS BLOCK: {ticker} reports in {delta} days ({earnings_date})"
        )

    return blocked, delta


def build_earnings_context(
    tickers: list[str], cfg: Config
) -> dict[str, dict[str, Any]]:
    """Build earnings context for all tickers.

    Returns per-ticker dict with:
    - next_earnings_date
    - days_until_earnings
    - is_blocked (within 5-day window)
    """
    log.info("Fetching earnings calendar")
    dates = fetch_all_earnings_dates(tickers, cfg)

    context: dict[str, dict[str, Any]] = {}
    for ticker in tickers:
        earnings_date = dates.get(ticker)
        blocked, days_until = is_earnings_blocked(ticker, earnings_date)
        context[ticker] = {
            "next_earnings_date": earnings_date,
            "days_until_earnings": days_until,
            "is_blocked": blocked,
        }

    blocked_count = sum(1 for v in context.values() if v["is_blocked"])
    log.info(f"Earnings calendar: {blocked_count}/{len(tickers)} stocks in blackout")

    return context
