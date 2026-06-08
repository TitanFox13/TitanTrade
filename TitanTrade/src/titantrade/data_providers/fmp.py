"""FMP data provider — the legacy single-source implementation (Financial
Modeling Prep).

RETAINED, NOT USED BY DEFAULT. The system replaced FMP with the ``native``
provider (Alpaca + FRED + Finnhub, ADR 040) to drop FMP's paid subscription.
This module preserves the original FMP fetchers behind the same interface so
the system can switch back at any time:

    DATA_PROVIDER=fmp   (env var; requires a valid FMP_KEY)

Implements the same functions as ``data_providers/native`` with identical
signatures and return shapes. Requires ``cfg.fmp.key``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from titantrade.config import Config
from titantrade.logger import get_logger
from titantrade.retry import fetch_with_retry

log = get_logger("data.fmp")

_STABLE = "https://financialmodelingprep.com/stable"


# ---------------------------------------------------------------------------
# Prices / quotes / news
# ---------------------------------------------------------------------------

def get_ohlcv(ticker: str, cfg: Config, days: int = 250) -> list[dict[str, Any]]:
    """Historical OHLCV from FMP, oldest-first."""
    today = datetime.now(timezone.utc).date()
    from_date = today - timedelta(days=int(days * 1.5))
    resp = fetch_with_retry("GET", f"{_STABLE}/historical-price-eod/full", params={
        "symbol": ticker, "from": from_date.isoformat(),
        "to": today.isoformat(), "apikey": cfg.fmp.key,
    })
    data = resp.json()
    historical = data if isinstance(data, list) else data.get("historical", [])
    bars = [
        {"date": b["date"], "open": b["open"], "high": b["high"],
         "low": b["low"], "close": b["close"], "volume": b["volume"]}
        for b in reversed(historical)
    ]
    return bars[-days:] if len(bars) > days else bars


def get_latest_price(ticker: str, cfg: Config) -> float | None:
    """Current price from FMP quote."""
    try:
        resp = fetch_with_retry("GET", f"{_STABLE}/quote", params={
            "symbol": ticker, "apikey": cfg.fmp.key,
        })
        data = resp.json()
        if data and isinstance(data, list) and data[0].get("price"):
            return float(data[0]["price"])
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Quote fetch failed for {ticker}: {exc}")
    return None


def get_daily_change_pct(ticker: str, cfg: Config) -> float | None:
    """Daily % change from FMP quote (changePercentage; falls back to
    price/previousClose)."""
    try:
        resp = fetch_with_retry("GET", f"{_STABLE}/quote", params={
            "symbol": ticker, "apikey": cfg.fmp.key,
        })
        data = resp.json()
        if data and isinstance(data, list):
            quote = data[0]
            change_pct = quote.get("changePercentage")
            if change_pct is not None:
                return round(float(change_pct), 2)
            price = quote.get("price", 0)
            prev_close = quote.get("previousClose", 0)
            if price and prev_close:
                return round((float(price) - float(prev_close)) / float(prev_close) * 100, 2)
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Daily change fetch failed for {ticker}: {exc}")
    return None


def get_news(ticker: str, cfg: Config, limit: int = 50) -> list[dict[str, Any]]:
    """Recent news from FMP. Shape: ``[{title, snippet, published_at,
    source}]`` (de-dup applied by the caller)."""
    try:
        resp = fetch_with_retry("GET", f"{_STABLE}/news/stock", params={
            "symbol": ticker, "limit": str(limit), "apikey": cfg.fmp.key,
        })
        articles = resp.json() or []
    except Exception as exc:  # noqa: BLE001
        log.warning(f"News fetch failed for {ticker}: {exc}")
        return []
    return [
        {
            "title": a.get("title", ""),
            "snippet": (a.get("text") or "")[:500],
            "published_at": a.get("publishedDate", ""),
            "source": a.get("site", ""),
        }
        for a in articles
    ]


# ---------------------------------------------------------------------------
# Macro — VIX, treasury, economic calendar
# ---------------------------------------------------------------------------

def get_vix(cfg: Config) -> float | None:
    """Current VIX level from FMP quote (^VIX)."""
    try:
        resp = fetch_with_retry("GET", f"{_STABLE}/quote", params={
            "symbol": "^VIX", "apikey": cfg.fmp.key,
        })
        data = resp.json()
        if data and isinstance(data, list):
            return data[0].get("price")
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Failed to fetch VIX: {exc}")
    return None


def get_treasury_yields(cfg: Config) -> dict[str, float | None]:
    """10Y and 2Y Treasury yields from FMP treasury-rates."""
    result: dict[str, float | None] = {"yield_10y": None, "yield_2y": None}
    try:
        resp = fetch_with_retry("GET", f"{_STABLE}/treasury-rates", params={
            "apikey": cfg.fmp.key,
        })
        data = resp.json()
        if data and isinstance(data, list):
            entry = data[0]
            result["yield_10y"] = entry.get("year10")
            result["yield_2y"] = entry.get("year2")
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Failed to fetch treasury yields: {exc}")
    return result


_HIGH_IMPACT_KEYWORDS = {
    "FOMC", "Federal Funds Rate", "Interest Rate Decision",
    "CPI", "Consumer Price Index", "Non-Farm", "Nonfarm", "Employment",
    "PPI", "Producer Price", "GDP", "Gross Domestic Product",
    "Retail Sales", "PCE", "Personal Consumption",
}


def get_economic_calendar(cfg: Config, days_ahead: int = 7) -> list[dict[str, Any]]:
    """Upcoming high-impact US macro events from FMP economic-calendar."""
    today = datetime.now(timezone.utc).date()
    try:
        resp = fetch_with_retry("GET", f"{_STABLE}/economic-calendar", params={
            "from": today.isoformat(),
            "to": (today + timedelta(days=days_ahead)).isoformat(),
            "apikey": cfg.fmp.key,
        })
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Economic calendar fetch failed: {exc}")
        return []
    events = []
    for entry in data:
        event_name = entry.get("event", "")
        if entry.get("country", "") != "US":
            continue
        if any(kw.lower() in event_name.lower() for kw in _HIGH_IMPACT_KEYWORDS):
            events.append({
                "date": entry.get("date", ""), "event": event_name,
                "impact": entry.get("impact", ""),
                "previous": entry.get("previous"), "estimate": entry.get("estimate"),
            })
    return events


# ---------------------------------------------------------------------------
# Per-ticker fundamentals — earnings, analyst, sector
# ---------------------------------------------------------------------------

def get_earnings_dates(tickers: list[str], cfg: Config) -> dict[str, str | None]:
    """Next earnings date per ticker from FMP earnings-calendar (one call)."""
    today = datetime.now(timezone.utc).date()
    result: dict[str, str | None] = {t: None for t in tickers}
    try:
        resp = fetch_with_retry("GET", f"{_STABLE}/earnings-calendar", params={
            "from": today.isoformat(),
            "to": (today + timedelta(days=60)).isoformat(),
            "apikey": cfg.fmp.key,
        })
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Failed to fetch earnings calendar: {exc}")
        return result
    ticker_set = set(tickers)
    for entry in data:
        symbol = entry.get("symbol", "")
        if symbol in ticker_set and result[symbol] is None:
            result[symbol] = entry.get("date")
    return result


def get_analyst_ratings(ticker: str, cfg: Config) -> dict[str, Any]:
    """Analyst consensus ratings and price targets from FMP."""
    result: dict[str, Any] = {}
    try:
        resp = fetch_with_retry("GET", f"{_STABLE}/grades", params={
            "symbol": ticker, "apikey": cfg.fmp.key, "limit": "10",
        })
        grades = resp.json()
        if grades and isinstance(grades, list):
            result["recent_grades"] = [
                {
                    "date": g.get("date", ""), "company": g.get("gradingCompany", ""),
                    "action": g.get("newGrade", ""), "previous": g.get("previousGrade", ""),
                }
                for g in grades[:10]
            ]
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Analyst grades fetch failed for {ticker}: {exc}")

    try:
        resp2 = fetch_with_retry("GET", f"{_STABLE}/price-target-consensus", params={
            "symbol": ticker, "apikey": cfg.fmp.key,
        })
        data = resp2.json()
        if data and isinstance(data, list) and data[0]:
            pt = data[0]
            result["price_target"] = {
                "consensus": pt.get("targetConsensus"), "high": pt.get("targetHigh"),
                "low": pt.get("targetLow"), "median": pt.get("targetMedian"),
            }
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Price target fetch failed for {ticker}: {exc}")
    return result


def get_sector(ticker: str, cfg: Config) -> str:
    """Company sector from FMP profile. 'Unknown' when unavailable."""
    try:
        resp = fetch_with_retry("GET", f"{_STABLE}/profile", params={
            "symbol": ticker, "apikey": cfg.fmp.key,
        })
        data = resp.json()
        if data and isinstance(data, list) and data[0].get("sector"):
            return data[0]["sector"]
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Failed to fetch sector for {ticker}: {exc}")
    return "Unknown"
