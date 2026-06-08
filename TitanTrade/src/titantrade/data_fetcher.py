"""Module A: Data-bundle assembler.

Pulls market data via the unified ``market_data`` layer (Alpaca + FRED +
Finnhub — see ADR 040; FMP fully replaced) and SEC EDGAR (filings), and
produces a clean JSON "Data Bundle" that includes:
  - OHLCV price data (250 days for indicator calculation, last 5 sent to Claude)
  - Technical indicators (RSI, MACD, Bollinger, ATR, SMA analysis)
  - News headlines and snippets (last 7 days)
  - SEC filings (8-K, 10-Q, 10-K from last 24 hours) — free EDGAR API
  - Market context (SPY, VIX, sector rotation)
  - Earnings calendar (upcoming dates + blackout flags)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from titantrade import market_data
from titantrade.config import Config, STATE_DIR, load_config
from titantrade.earnings import build_earnings_context
from titantrade.indicators import atr as compute_atr
from titantrade.indicators import compute_all_indicators
from titantrade.logger import get_logger
from titantrade.market_context import load_stock_sectors
from titantrade.market_context import build_market_context
from titantrade.sec_edgar import fetch_insider_filings, fetch_recent_filings

log = get_logger("data_fetcher")

# We fetch 250 days for indicator computation but only send last 5 to Claude
HISTORY_DAYS = 250
DISPLAY_DAYS = 5


def fetch_ohlcv(
    ticker: str, cfg: Config, days: int = HISTORY_DAYS
) -> list[dict[str, Any]]:
    """Historical OHLCV (Alpaca data API). Returns oldest-first."""
    log.info(f"Fetching OHLCV for {ticker} ({days} days)")
    return market_data.get_ohlcv(ticker, cfg, days=days)


def _news_dedup_key(title: str) -> str:
    """Normalize a headline for syndication-aware dedup.

    Wires routinely republish the same story under near-identical titles
    across dozens of outlets ("Apple Reports Strong Q2" / "Apple Reports
    Strong Q2 Earnings" / "AAPL: Apple Reports Strong Q2"). An exact-title
    set caught only the byte-identical cases. We normalize aggressively:
    lowercase, keep only alphanumeric + spaces, collapse whitespace, take
    the first 60 chars. That treats those three as the same story while
    still distinguishing genuinely-different headlines that diverge early.
    """
    import re
    if not title:
        return ""
    norm = re.sub(r"[^a-z0-9\s]", "", title.lower())
    norm = " ".join(norm.split())  # collapse whitespace
    return norm[:60]


def fetch_news(ticker: str, cfg: Config, limit: int = 50) -> list[dict[str, Any]]:
    """Pull recent news headlines and snippets from FMP.

    De-duplication is more aggressive than exact-title match — wire
    syndication inflates apparent news volume by 5-10x and was causing
    both the analyst and sentry to over-weight single events that appeared
    to be "10 separate concerns".
    """
    log.info(f"Fetching news for {ticker}")
    articles = market_data.get_news(ticker, cfg, limit=limit)

    seen_keys: set[str] = set()
    results: list[dict[str, Any]] = []
    duplicates = 0
    for article in articles:
        key = _news_dedup_key(article.get("title", ""))
        if not key or key in seen_keys:
            duplicates += 1
            continue
        seen_keys.add(key)
        results.append(article)

    if duplicates > 0:
        log.info(f"News dedup for {ticker}: removed {duplicates} syndicated duplicate(s)")

    return results


def fetch_sec_filings(ticker: str) -> list[dict[str, Any]]:
    """Recent SEC filings (8-K, 10-Q, 10-K) from the free SEC EDGAR API."""
    log.info(f"Fetching SEC filings for {ticker}")
    return fetch_recent_filings(
        ticker,
        form_types=("8-K", "10-Q", "10-K"),
        days_back=1,
        limit=10,
    )


def fetch_analyst_ratings(ticker: str, cfg: Config) -> dict[str, Any]:
    """Analyst recommendation trend (Finnhub). Price-target consensus has no
    free source post-FMP and is omitted; the buy/hold/sell mix is preserved."""
    return market_data.get_analyst_ratings(ticker, cfg)


def fetch_insider_trades(ticker: str) -> list[dict[str, Any]]:
    """Recent Form 4 insider filings from the free SEC EDGAR API.

    Returns the last 30 days of Form 4 filings. Note that the free submissions
    endpoint does not include reporting-owner names without parsing each filing's
    XML — the `insider_name` field is left blank. The weekly analyst primarily
    uses the *count* and *timing* of insider activity as a signal.
    """
    return fetch_insider_filings(ticker, days_back=30, limit=10)


def fetch_economic_calendar(cfg: Config, days_ahead: int = 7) -> list[dict[str, Any]]:
    """Upcoming high-impact US macro events (FRED releases + FOMC schedule).

    Returns high-impact events in the next N days. Empty when the FRED key is
    absent — the macro-blackout gate fails open, as it did on FMP errors.
    """
    return market_data.get_economic_calendar(cfg, days_ahead=days_ahead)


def build_stock_data(ticker: str, cfg: Config) -> dict[str, Any]:
    """Build complete data for a single stock: prices, indicators, news, filings."""
    # Fetch full history for indicators
    all_bars = fetch_ohlcv(ticker, cfg, days=HISTORY_DAYS)

    # Compute indicators from full history
    indicators = compute_all_indicators(all_bars) if len(all_bars) >= 20 else {}

    # Extract ATR separately for position sizing (used by risk_manager)
    stock_atr = compute_atr(all_bars) if len(all_bars) >= 15 else None

    # Only send last N days of OHLCV to Claude (it doesn't need 250 candles)
    recent_bars = all_bars[-DISPLAY_DAYS:] if len(all_bars) > DISPLAY_DAYS else all_bars

    return {
        "ohlcv_recent": recent_bars,
        "ohlcv_full": all_bars,  # Kept for correlation/RS computation
        "technical_indicators": indicators,
        "atr_14": stock_atr,
        "news": fetch_news(ticker, cfg),
        "sec_filings": fetch_sec_filings(ticker),
        "insider_trades": fetch_insider_trades(ticker),
        "analyst_ratings": fetch_analyst_ratings(ticker, cfg),
    }


def build_data_bundle(cfg: Config) -> dict[str, Any]:
    """Assemble the complete data bundle for all watchlist stocks.

    Includes per-stock data, market context, and earnings calendar.
    """
    log.info(f"Building data bundle for {len(cfg.trading.watchlist)} stocks")

    # Load/cache sector mappings for all watchlist tickers (dynamic via FMP)
    sectors = load_stock_sectors(cfg.trading.watchlist, cfg)
    log.info(f"Sector map: {sectors}")

    # Fetch market context (SPY, VIX, sectors)
    try:
        market_ctx = build_market_context(cfg)
    except Exception as exc:
        log.error(f"Market context fetch failed: {exc}")
        market_ctx = {"error": str(exc)}

    # Fetch earnings calendar for all watchlist stocks
    try:
        earnings_ctx = build_earnings_context(cfg.trading.watchlist, cfg)
    except Exception as exc:
        log.error(f"Earnings calendar fetch failed: {exc}")
        earnings_ctx = {}

    # Build per-stock data
    stocks: dict[str, Any] = {}
    for ticker in cfg.trading.watchlist:
        log.info(f"Building data for {ticker}")
        try:
            stock_data = build_stock_data(ticker, cfg)
            stock_data["earnings"] = earnings_ctx.get(ticker, {})
            stocks[ticker] = stock_data
        except Exception as exc:
            log.error(f"Failed to fetch data for {ticker}: {exc}")
            stocks[ticker] = {
                "ohlcv_recent": [],
                "technical_indicators": {},
                "atr_14": None,
                "news": [],
                "sec_filings": [],
                "earnings": earnings_ctx.get(ticker, {}),
                "error": str(exc),
            }

    # Fetch economic calendar (macro events)
    try:
        macro_events = fetch_economic_calendar(cfg, days_ahead=7)
        if macro_events:
            log.info(f"Macro events in next 7 days: {[e['event'] for e in macro_events]}")
    except Exception as exc:
        log.error(f"Economic calendar fetch failed: {exc}")
        macro_events = []

    # Compute relative strength vs SPY for each stock
    from titantrade.indicators import relative_strength, correlation

    spy_bars = market_ctx.pop("_spy_bars", [])
    closes_map: dict[str, list[float]] = {}

    for ticker, stock_data in stocks.items():
        full_bars = stock_data.pop("ohlcv_full", [])
        closes_map[ticker] = [b["close"] for b in full_bars] if full_bars else []
        if full_bars and spy_bars:
            stock_data["relative_strength_vs_spy"] = relative_strength(full_bars, spy_bars)

    # Pairwise correlation matrix (60-day) across watchlist for Pass 2
    tickers_list = [t for t in cfg.trading.watchlist if len(closes_map.get(t, [])) >= 60]
    corr_matrix: dict[str, dict[str, float]] = {}
    for i, t1 in enumerate(tickers_list):
        for t2 in tickers_list[i + 1:]:
            c = correlation(closes_map[t1], closes_map[t2], period=60)
            if c is not None:
                corr_matrix.setdefault(t1, {})[t2] = c
                corr_matrix.setdefault(t2, {})[t1] = c

    bundle: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market_context": market_ctx,
        "economic_calendar": macro_events,
        "correlation_matrix": corr_matrix,
        "stocks": stocks,
    }

    return bundle


def save_data_bundle(bundle: dict[str, Any]) -> None:
    """Save the data bundle to state directory."""
    path = STATE_DIR / "data_bundle.json"
    with open(path, "w") as f:
        json.dump(bundle, f, indent=2)
    log.info(f"Data bundle saved to {path}")


def main() -> None:
    """Entry point: fetch all data and save the bundle."""
    cfg = load_config()
    bundle = build_data_bundle(cfg)
    save_data_bundle(bundle)

    stock_count = len(bundle["stocks"])
    regime = bundle.get("market_context", {}).get("market_regime", "unknown")
    log.info(f"Data bundle complete: {stock_count} stocks, market regime: {regime}")


if __name__ == "__main__":
    main()
