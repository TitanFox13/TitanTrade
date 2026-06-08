"""Market-data facade — dispatches to the configured data provider.

All consumers (data_fetcher, market_context, earnings, daily_sentry, backtest)
call these functions and never import a provider directly. The active provider
is chosen by ``cfg.data_provider`` (env ``DATA_PROVIDER``):

  - ``native`` (default) — Alpaca + FRED + Finnhub (free; ADR 040).
  - ``fmp``              — legacy Financial Modeling Prep (retained; set
                           ``DATA_PROVIDER=fmp`` + a valid ``FMP_KEY``).

See ``titantrade.data_providers`` for the interface contract.
"""

from __future__ import annotations

from typing import Any

from titantrade.config import Config
from titantrade.data_providers import fmp, native
from titantrade.logger import get_logger

log = get_logger("market_data")

_PROVIDERS = {"native": native, "fmp": fmp}


def _provider(cfg: Config):
    """Resolve the active provider module from config (default ``native``)."""
    name = (getattr(cfg, "data_provider", None) or "native").lower()
    provider = _PROVIDERS.get(name)
    if provider is None:
        log.warning(f"Unknown data_provider {name!r}; falling back to 'native'")
        return native
    return provider


# --- Prices / quotes / news -------------------------------------------------

def get_ohlcv(ticker: str, cfg: Config, days: int = 250) -> list[dict[str, Any]]:
    return _provider(cfg).get_ohlcv(ticker, cfg, days=days)


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
