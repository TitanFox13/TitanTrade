"""Module A: Data fetcher for FMP (prices + news) and SEC-API (filings).

Produces a clean JSON "Data Bundle" that includes:
  - OHLCV price data (250 days for indicator calculation, last 5 sent to Claude)
  - Technical indicators (RSI, MACD, Bollinger, ATR, SMA analysis)
  - News headlines and snippets (last 7 days)
  - SEC filings (8-K, 10-Q, 10-K from last 24 hours)
  - Market context (SPY, VIX, sector rotation)
  - Earnings calendar (upcoming dates + blackout flags)
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from titantrade.config import Config, STATE_DIR, load_config
from titantrade.earnings import build_earnings_context
from titantrade.indicators import atr as compute_atr
from titantrade.indicators import compute_all_indicators
from titantrade.logger import get_logger
from titantrade.market_context import load_stock_sectors
from titantrade.market_context import build_market_context
from titantrade.retry import fetch_with_retry

log = get_logger("data_fetcher")

# We fetch 250 days for indicator computation but only send last 5 to Claude
HISTORY_DAYS = 250
DISPLAY_DAYS = 5


def fetch_ohlcv(
    ticker: str, cfg: Config, days: int = HISTORY_DAYS
) -> list[dict[str, Any]]:
    """Pull historical OHLCV data from FMP. Returns oldest-first."""
    today = datetime.now(timezone.utc).date()
    from_date = today - timedelta(days=int(days * 1.5))  # pad for weekends

    url = f"{cfg.fmp.base_url}/historical-price-full/{ticker}"
    params = {
        "from": from_date.isoformat(),
        "to": today.isoformat(),
        "apikey": cfg.fmp.key,
    }

    log.info(f"Fetching OHLCV for {ticker} ({days} days)")
    resp = fetch_with_retry("GET", url, params=params)
    data = resp.json()

    historical = data.get("historical", [])
    # FMP returns newest-first, reverse to oldest-first
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
    return bars[-days:] if len(bars) > days else bars


def fetch_news(ticker: str, cfg: Config, limit: int = 50) -> list[dict[str, Any]]:
    """Pull recent news headlines and snippets from FMP."""
    url = f"{cfg.fmp.base_url}/stock_news"
    params = {
        "tickers": ticker,
        "limit": str(limit),
        "apikey": cfg.fmp.key,
    }

    log.info(f"Fetching news for {ticker}")
    resp = fetch_with_retry("GET", url, params=params)
    articles = resp.json()

    # Deduplicate by title
    seen_titles: set[str] = set()
    results: list[dict[str, Any]] = []
    for article in articles:
        title = article.get("title", "")
        if title in seen_titles:
            continue
        seen_titles.add(title)
        results.append({
            "title": title,
            "snippet": article.get("text", "")[:500],
            "published_at": article.get("publishedDate", ""),
            "source": article.get("site", ""),
        })

    return results


def fetch_sec_filings(ticker: str, cfg: Config) -> list[dict[str, Any]]:
    """Check for recent SEC filings (8-K, 10-Q, 10-K) from SEC-API.io."""
    url = f"{cfg.sec_api.base_url}/v1/filings"
    params = {"token": cfg.sec_api.key}

    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )

    query_body = {
        "query": {
            "query_string": {
                "query": (
                    f'ticker:"{ticker}" AND '
                    f'(formType:"8-K" OR formType:"10-Q" OR formType:"10-K") AND '
                    f'filedAt:{{{yesterday} TO *}}'
                )
            }
        },
        "from": "0",
        "size": "10",
        "sort": [{"filedAt": {"order": "desc"}}],
    }

    log.info(f"Fetching SEC filings for {ticker}")
    try:
        resp = fetch_with_retry("POST", url, params=params, json_body=query_body)
        data = resp.json()
    except Exception as exc:
        log.warning(f"SEC-API failed for {ticker}: {exc}")
        return []

    filings = data.get("filings", [])
    return [
        {
            "form_type": f.get("formType", ""),
            "filed_at": f.get("filedAt", ""),
            "description": f.get("description", ""),
            "url": f.get("linkToHtml", ""),
        }
        for f in filings
    ]


def fetch_analyst_ratings(ticker: str, cfg: Config) -> dict[str, Any]:
    """Fetch analyst consensus ratings and price targets from FMP."""
    result: dict[str, Any] = {}

    # Consensus ratings
    url = f"{cfg.fmp.base_url}/grade/{ticker}"
    params = {"apikey": cfg.fmp.key, "limit": "10"}
    try:
        resp = fetch_with_retry("GET", url, params=params)
        grades = resp.json()
        if grades and isinstance(grades, list):
            recent = grades[:10]
            result["recent_grades"] = [
                {
                    "date": g.get("date", ""),
                    "company": g.get("gradingCompany", ""),
                    "action": g.get("newGrade", ""),
                    "previous": g.get("previousGrade", ""),
                }
                for g in recent
            ]
    except Exception as exc:
        log.warning(f"Analyst grades fetch failed for {ticker}: {exc}")

    # Price target consensus
    url2 = f"{cfg.fmp.base_url}/price-target-consensus/{ticker}"
    params2 = {"apikey": cfg.fmp.key}
    try:
        resp2 = fetch_with_retry("GET", url2, params=params2)
        data = resp2.json()
        if data and isinstance(data, list) and data[0]:
            pt = data[0]
            result["price_target"] = {
                "consensus": pt.get("targetConsensus"),
                "high": pt.get("targetHigh"),
                "low": pt.get("targetLow"),
                "median": pt.get("targetMedian"),
            }
    except Exception as exc:
        log.warning(f"Price target fetch failed for {ticker}: {exc}")

    return result


def fetch_insider_trades(ticker: str, cfg: Config) -> list[dict[str, Any]]:
    """Fetch recent Form 4 insider trades via SEC-API.

    Returns structured list of insider buys/sells from the last 30 days.
    """
    if not cfg.sec_api.key:
        return []

    url = f"{cfg.sec_api.base_url}/v1/filings"
    params = {"token": cfg.sec_api.key}

    from_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )

    query_body = {
        "query": {
            "query_string": {
                "query": (
                    f'ticker:"{ticker}" AND formType:"4" AND '
                    f'filedAt:{{{from_date} TO *}}'
                )
            }
        },
        "from": "0",
        "size": "10",
        "sort": [{"filedAt": {"order": "desc"}}],
    }

    try:
        resp = fetch_with_retry("POST", url, params=params, json_body=query_body)
        data = resp.json()
    except Exception as exc:
        log.warning(f"SEC-API Form 4 fetch failed for {ticker}: {exc}")
        return []

    filings = data.get("filings", [])
    results = []
    for f in filings:
        results.append({
            "filed_at": f.get("filedAt", ""),
            "insider_name": f.get("reportingOwner", {}).get("name", "") if isinstance(f.get("reportingOwner"), dict) else "",
            "description": f.get("description", ""),
            "url": f.get("linkToHtml", ""),
        })

    return results


def fetch_economic_calendar(cfg: Config, days_ahead: int = 7) -> list[dict[str, Any]]:
    """Fetch upcoming macro events (FOMC, CPI, jobs, GDP, PPI) from FMP.

    Returns list of high-impact events in the next N days.
    """
    today = datetime.now(timezone.utc).date()
    url = f"{cfg.fmp.base_url}/economic_calendar"
    params = {
        "from": today.isoformat(),
        "to": (today + timedelta(days=days_ahead)).isoformat(),
        "apikey": cfg.fmp.key,
    }

    HIGH_IMPACT_KEYWORDS = {
        "FOMC", "Federal Funds Rate", "Interest Rate Decision",
        "CPI", "Consumer Price Index",
        "Non-Farm", "Nonfarm", "Employment",
        "PPI", "Producer Price",
        "GDP", "Gross Domestic Product",
        "Retail Sales",
        "PCE", "Personal Consumption",
    }

    try:
        resp = fetch_with_retry("GET", url, params=params)
        data = resp.json()
    except Exception as exc:
        log.warning(f"Economic calendar fetch failed: {exc}")
        return []

    events = []
    for entry in data:
        event_name = entry.get("event", "")
        country = entry.get("country", "")
        if country != "US":
            continue
        if any(kw.lower() in event_name.lower() for kw in HIGH_IMPACT_KEYWORDS):
            events.append({
                "date": entry.get("date", ""),
                "event": event_name,
                "impact": entry.get("impact", ""),
                "previous": entry.get("previous"),
                "estimate": entry.get("estimate"),
            })

    return events


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
        "sec_filings": fetch_sec_filings(ticker, cfg),
        "insider_trades": fetch_insider_trades(ticker, cfg),
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
