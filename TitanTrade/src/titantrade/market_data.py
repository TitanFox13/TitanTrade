"""Market-data facade over the native provider (Alpaca + FRED + Finnhub, ADR 040).

All consumers call these functions and never import the provider directly.
"""

from __future__ import annotations

from typing import Any

from titantrade.config import Config
from titantrade.data_providers import native
from titantrade.logger import get_logger

log = get_logger("market_data")

def _provider(cfg: Config):
    return native


# --- Prices / quotes / news -------------------------------------------------

def get_ohlcv(
    ticker: str, cfg: Config, days: int = 250, feed: str | None = None,
) -> list[dict[str, Any]]:
    """Daily OHLCV. ``feed`` (Alpaca-only) overrides the configured data feed
    for this call — e.g. ``"sip"`` when today's close must be present."""
    return _provider(cfg).get_ohlcv(ticker, cfg, days=days, feed=feed)


def get_latest_price(ticker: str, cfg: Config) -> float | None:
    return _provider(cfg).get_latest_price(ticker, cfg)


def get_daily_change_pct(ticker: str, cfg: Config) -> float | None:
    return _provider(cfg).get_daily_change_pct(ticker, cfg)


def get_news(ticker: str, cfg: Config, limit: int = 50) -> list[dict[str, Any]]:
    return _provider(cfg).get_news(ticker, cfg, limit=limit)


# --- Macro ------------------------------------------------------------------

def get_vix(cfg: Config) -> float | None:
    return _provider(cfg).get_vix(cfg)


def get_treasury_yields(cfg: Config) -> dict[str, float | None]:
    return _provider(cfg).get_treasury_yields(cfg)


def get_economic_calendar(cfg: Config, days_ahead: int = 7) -> list[dict[str, Any]]:
    return _provider(cfg).get_economic_calendar(cfg, days_ahead=days_ahead)


# --- Per-ticker fundamentals ------------------------------------------------

def get_earnings_dates(tickers: list[str], cfg: Config) -> dict[str, str | None]:
    return _provider(cfg).get_earnings_dates(tickers, cfg)


def get_analyst_ratings(ticker: str, cfg: Config) -> dict[str, Any]:
    return _provider(cfg).get_analyst_ratings(ticker, cfg)


def get_sector(ticker: str, cfg: Config) -> str:
    return _provider(cfg).get_sector(ticker, cfg)
