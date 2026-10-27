"""Market-wide inputs: SPY and the sector breadth behind the insurance switch,
plus the per-ticker sector cache the sector-exposure gate uses.

Sector mapping is dynamic (Finnhub) and cached in ``state/sector_cache.json``,
so the watchlist can change without code changes.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from titantrade import market_data
from titantrade.config import STATE_DIR, Config
from titantrade.logger import get_logger

log = get_logger("market_context")

_sector_cache: dict[str, str] = {}


def _sector_cache_path():
    return STATE_DIR / "sector_cache.json"


def _load_sector_cache() -> dict[str, str]:
    path = _sector_cache_path()
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def _save_sector_cache(cache: dict[str, str]) -> None:
    with open(_sector_cache_path(), "w") as f:
        json.dump(cache, f, indent=2)


def load_stock_sectors(tickers: list[str], cfg: Config) -> dict[str, str]:
    """Sectors for all tickers, fetching (Finnhub) and caching any unknown ones."""
    global _sector_cache
    if not _sector_cache:
        _sector_cache = _load_sector_cache()
    missing = [t for t in tickers if t not in _sector_cache]
    if missing:
        log.info(f"Fetching sectors for {len(missing)} new tickers: {missing}")
        for ticker in missing:
            _sector_cache[ticker] = market_data.get_sector(ticker, cfg)
        _save_sector_cache(_sector_cache)
    return {t: _sector_cache.get(t, "Unknown") for t in tickers}


def get_stock_sector(ticker: str) -> str:
    """Cached sector for a stock; 'Unknown' if not yet loaded."""
    return _sector_cache.get(ticker, "Unknown")


def _fetch_bars(ticker: str, cfg: Config, days: int = 250) -> list[dict[str, Any]]:
    return market_data.get_ohlcv(ticker, cfg, days=days)


def _compute_return(bars: list[dict[str, Any]], days: int) -> float | None:
    if len(bars) < days + 1:
        return None
    old, new = bars[-(days + 1)]["close"], bars[-1]["close"]
    return round((new - old) / old * 100, 2) if old else None


def sector_breadth(cfg: Config, spy_bars: list[dict[str, Any]]) -> dict[str, Any]:
    """Insurance inputs (Decision 061): share of sector ETFs above their SMA
    and whether SPY is above its own. A failed ETF fetch leaves that ETF out
    of the count (fails open toward full exposure)."""
    from titantrade.signals import above_sma_flags, breadth, sma

    n = cfg.trading.insurance_sma_days
    series: dict[str, list[float]] = {}
    for etf in cfg.trading.sector_etfs:
        try:
            series[etf] = [b["close"] for b in _fetch_bars(etf, cfg, days=250)]
        except Exception as exc:  # noqa: BLE001
            log.warning(f"Breadth: bars for {etf} failed: {exc}")
    flags = above_sma_flags(series, n)
    spy_closes = [b["close"] for b in spy_bars]
    spy_sma = sma(spy_closes, n)
    return {
        "sma_days": n,
        "sectors_above": sum(1 for f in flags.values() if f),
        "sectors_total": sum(1 for f in flags.values() if f is not None),
        "pct": breadth(flags.values()),
        "flags": flags,
        "spy_close": spy_closes[-1] if spy_closes else None,
        "spy_sma": round(spy_sma, 2) if spy_sma else None,
        "spy_above_sma": (spy_closes[-1] > spy_sma) if (spy_closes and spy_sma) else None,
    }


def build_market_context(cfg: Config) -> dict[str, Any]:
    """SPY snapshot + the insurance inputs. ``_spy_bars`` is for the caller
    and is stripped before the bundle is saved."""
    log.info("Building market context")
    spy_bars = _fetch_bars("SPY", cfg, days=250)
    context: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "spy": {
            "close": spy_bars[-1]["close"] if spy_bars else None,
            "return_1d": _compute_return(spy_bars, 1),
            "return_5d": _compute_return(spy_bars, 5),
            "return_20d": _compute_return(spy_bars, 20),
            # the shock trigger's window (Decision 068), read by the plan
            "closes": [b["close"] for b in spy_bars[-(cfg.trading.shock_lookback_days + cfg.trading.shock_hold_days + 1):]],
        },
    }
    try:
        context["breadth"] = sector_breadth(cfg, spy_bars)
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Sector breadth failed (insurance fails open): {exc}")
        context["breadth"] = {}
    context["_spy_bars"] = spy_bars
    b = context["breadth"]
    log.info(f"SPY {context['spy']['close']} (above SMA: {b.get('spy_above_sma')}) | sector breadth {b.get('pct')}")
    return context
