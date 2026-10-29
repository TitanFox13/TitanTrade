"""Data bundle: everything the plan and the gates need, nothing the LLMs needed.

Per watchlist name: the three numbers of the entry rule (``signal_inputs``:
last close, lookback high, trend SMA — computed here from the full 250-day
history because only the last few bars are saved), ATR-14, the earnings
blackout and the sector. Market-wide: SPY, the sector-breadth inputs of the
insurance switch, the macro calendar (macro-blackout gate) and the 60-day
correlation matrix (correlation gate).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from titantrade import market_data
from titantrade.config import STATE_DIR, Config, load_config
from titantrade.earnings import build_earnings_context
from titantrade.indicators import atr as compute_atr
from titantrade.indicators import correlation
from titantrade.logger import get_logger
from titantrade.market_context import build_market_context, load_stock_sectors
from titantrade.signals import rolling_high, sma

log = get_logger("data_fetcher")

HISTORY_DAYS = 250   # enough for a 200-day SMA
DISPLAY_DAYS = 5     # bars kept in the bundle for the dashboard


def fetch_ohlcv(ticker: str, cfg: Config, days: int = HISTORY_DAYS) -> list[dict[str, Any]]:
    """Historical OHLCV (Alpaca data API), oldest first."""
    log.info(f"Fetching OHLCV for {ticker} ({days} days)")
    return market_data.get_ohlcv(ticker, cfg, days=days)


def fetch_economic_calendar(cfg: Config, days_ahead: int = 7) -> list[dict[str, Any]]:
    """Upcoming high-impact US macro events (FRED releases + FOMC schedule).
    Empty without a FRED key — the macro-blackout gate then fails open."""
    return market_data.get_economic_calendar(cfg, days_ahead=days_ahead)


def build_stock_data(ticker: str, cfg: Config) -> dict[str, Any]:
    """Prices, signal inputs and ATR for one name."""
    all_bars = fetch_ohlcv(ticker, cfg, days=HISTORY_DAYS)
    closes = [b["close"] for b in all_bars]
    return {
        "ohlcv_recent": all_bars[-DISPLAY_DAYS:],
        "ohlcv_full": all_bars,   # popped before saving; used for correlations
        "atr_14": compute_atr(all_bars) if len(all_bars) >= 15 else None,
        "signal_inputs": {
            "close": closes[-1] if closes else None,
            "high_lookback": rolling_high(closes, cfg.trading.dip_lookback_days),
            "sma_trend": sma(closes, cfg.trading.trend_sma_days),
            "lookback_days": cfg.trading.dip_lookback_days,
            "trend_sma_days": cfg.trading.trend_sma_days,
        },
    }


def bundle_names(cfg: Config) -> list[str]:
    """Watchlist first, then any shadow-list name not already in it."""
    return list(dict.fromkeys(list(cfg.trading.watchlist) + list(cfg.trading.shadow_watchlist)))


def build_data_bundle(cfg: Config) -> dict[str, Any]:
    """Assemble the bundle for all watchlist names (and the shadow list, which
    the curator reads — the plan only looks at the watchlist)."""
    names = bundle_names(cfg)
    log.info(f"Building data bundle for {len(names)} stocks")
    sectors = load_stock_sectors(names, cfg)

    try:
        market_ctx = build_market_context(cfg)
    except Exception as exc:  # noqa: BLE001
        log.error(f"Market context fetch failed: {exc}")
        market_ctx = {"error": str(exc)}
    try:
        earnings_ctx = build_earnings_context(names, cfg)
    except Exception as exc:  # noqa: BLE001
        log.error(f"Earnings calendar fetch failed: {exc}")
        earnings_ctx = {}

    stocks: dict[str, Any] = {}
    for ticker in names:
        try:
            stock = build_stock_data(ticker, cfg)
        except Exception as exc:  # noqa: BLE001
            log.error(f"Failed to fetch data for {ticker}: {exc}")
            stock = {"ohlcv_recent": [], "ohlcv_full": [], "atr_14": None, "signal_inputs": {}, "error": str(exc)}
        stock["earnings"] = earnings_ctx.get(ticker, {})
        stock["sector"] = sectors.get(ticker, "Unknown")
        stocks[ticker] = stock

    try:
        macro_events = fetch_economic_calendar(cfg, days_ahead=7)
        if macro_events:
            log.info(f"Macro events in next 7 days: {[e['event'] for e in macro_events]}")
    except Exception as exc:  # noqa: BLE001
        log.error(f"Economic calendar fetch failed: {exc}")
        macro_events = []

    market_ctx.pop("_spy_bars", None)
    closes_map = {t: [b["close"] for b in s.pop("ohlcv_full", [])] for t, s in stocks.items()}
    tickers_list = [t for t in names if len(closes_map.get(t, [])) >= 60]
    corr_matrix: dict[str, dict[str, float]] = {}
    for i, t1 in enumerate(tickers_list):
        for t2 in tickers_list[i + 1:]:
            c = correlation(closes_map[t1], closes_map[t2], period=60)
            if c is not None:
                corr_matrix.setdefault(t1, {})[t2] = c
                corr_matrix.setdefault(t2, {})[t1] = c

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market_context": market_ctx,
        "economic_calendar": macro_events,
        "correlation_matrix": corr_matrix,
        "stocks": stocks,
    }


def save_data_bundle(bundle: dict[str, Any]) -> None:
    path = STATE_DIR / "data_bundle.json"
    with open(path, "w") as f:
        json.dump(bundle, f, indent=2)
    log.info(f"Data bundle saved to {path}")


def main() -> None:
    cfg = load_config()
    bundle = build_data_bundle(cfg)
    save_data_bundle(bundle)
    breadth = (bundle.get("market_context") or {}).get("breadth") or {}
    log.info(
        f"Data bundle complete: {len(bundle['stocks'])} stocks | SPY above SMA: "
        f"{breadth.get('spy_above_sma')} | sector breadth: {breadth.get('pct')}"
    )


if __name__ == "__main__":
    main()
