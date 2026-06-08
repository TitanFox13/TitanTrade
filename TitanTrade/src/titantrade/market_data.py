"""Unified market-data layer — the FMP replacement (ADR 040).

Sources, each behind a small function with the SAME return shape the old FMP
fetchers produced, so the connectors in data_fetcher / market_context /
earnings / daily_sentry only change which function they call:

  - **Alpaca** data API (``data.alpaca.markets``, existing keys, free IEX feed):
    OHLCV bars, latest trade price, daily change %, news. The robust core.
  - **FRED** (St. Louis Fed, free key): VIX, treasury yields, economic-release
    calendar. Official macro data.
  - **Finnhub** (free key): per-ticker earnings dates, analyst recommendation
    trends, sector/industry. Best-effort enrichment.

Every function degrades gracefully — returns ``[]`` / ``None`` / ``{}`` on any
error or missing key — so a provider outage never crashes the pipeline. This
preserves FMP's prior fail-open behaviour (the macro/earnings gates already
treat missing data as "skip").
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from titantrade.config import Config, DATA_DIR
from titantrade.logger import get_logger
from titantrade.retry import fetch_with_retry

log = get_logger("market_data")

_YF_UA = {"User-Agent": "Mozilla/5.0 (TitanTrade)"}


# ---------------------------------------------------------------------------
# Alpaca data API — bars, quotes, news (core)
# ---------------------------------------------------------------------------

def _alpaca_data_headers(cfg: Config) -> dict[str, str]:
    return {
        "APCA-API-KEY-ID": cfg.alpaca.key,
        "APCA-API-SECRET-KEY": cfg.alpaca.secret,
    }


def get_ohlcv(ticker: str, cfg: Config, days: int = 250) -> list[dict[str, Any]]:
    """Historical daily OHLCV from Alpaca, oldest-first.

    Same shape as the old FMP fetcher: ``[{date, open, high, low, close,
    volume}]``. Alpaca returns ascending (oldest-first) already.
    """
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=int(days * 1.6))  # pad for weekends/holidays
    url = f"{cfg.alpaca.data_base_url}/v2/stocks/{ticker}/bars"
    params = {
        "timeframe": "1Day",
        "start": start.isoformat(),
        "end": today.isoformat(),
        "limit": "10000",
        "adjustment": "split",
        "feed": cfg.alpaca.data_feed,
    }
    bars: list[dict[str, Any]] = []
    page_token: str | None = None
    while True:
        if page_token:
            params["page_token"] = page_token
        resp = fetch_with_retry("GET", url, headers=_alpaca_data_headers(cfg), params=params)
        data = resp.json()
        for b in data.get("bars", []) or []:
            bars.append({
                "date": str(b["t"])[:10],   # "2026-05-01T04:00:00Z" -> "2026-05-01"
                "open": b["o"],
                "high": b["h"],
                "low": b["l"],
                "close": b["c"],
                "volume": b["v"],
            })
        page_token = data.get("next_page_token")
        if not page_token:
            break
    return bars[-days:] if len(bars) > days else bars


def get_latest_price(ticker: str, cfg: Config) -> float | None:
    """Latest trade price from Alpaca (lightweight; replaces FMP quote.price)."""
    url = f"{cfg.alpaca.data_base_url}/v2/stocks/{ticker}/trades/latest"
    try:
        resp = fetch_with_retry(
            "GET", url, headers=_alpaca_data_headers(cfg),
            params={"feed": cfg.alpaca.data_feed},
        )
        price = resp.json().get("trade", {}).get("p")
        return float(price) if price else None
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Latest price fetch failed for {ticker}: {exc}")
    return None


def get_daily_change_pct(ticker: str, cfg: Config) -> float | None:
    """Today's % change vs the previous daily close, from the Alpaca snapshot.

    Replaces FMP quote.changePercentage (used for the SPY market-wide check).
    """
    url = f"{cfg.alpaca.data_base_url}/v2/stocks/{ticker}/snapshot"
    try:
        resp = fetch_with_retry(
            "GET", url, headers=_alpaca_data_headers(cfg),
            params={"feed": cfg.alpaca.data_feed},
        )
        snap = resp.json()
        # Prefer latest trade vs previous daily close; fall back to daily bar.
        last = (snap.get("latestTrade") or {}).get("p")
        prev_close = (snap.get("prevDailyBar") or {}).get("c")
        if not last:
            last = (snap.get("dailyBar") or {}).get("c")
        if last and prev_close:
            return round((float(last) - float(prev_close)) / float(prev_close) * 100, 2)
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Daily change fetch failed for {ticker}: {exc}")
    return None


def get_news(ticker: str, cfg: Config, limit: int = 50) -> list[dict[str, Any]]:
    """Recent news from Alpaca's News API (Benzinga-sourced, free).

    Returns ``[{title, snippet, published_at, source}]`` — the same shape the
    old FMP fetcher produced (de-dup is applied by the caller).
    """
    url = f"{cfg.alpaca.data_base_url}/v1beta1/news"
    params = {"symbols": ticker, "limit": str(min(limit, 50)), "sort": "desc"}
    try:
        resp = fetch_with_retry("GET", url, headers=_alpaca_data_headers(cfg), params=params)
        articles = resp.json().get("news", []) or []
    except Exception as exc:  # noqa: BLE001
        log.warning(f"News fetch failed for {ticker}: {exc}")
        return []
    return [
        {
            "title": a.get("headline", ""),
            "snippet": (a.get("summary") or "")[:500],
            "published_at": a.get("created_at", ""),
            "source": a.get("source", ""),
        }
        for a in articles
    ]


# ---------------------------------------------------------------------------
# FRED — VIX, treasury, economic calendar (macro)
# ---------------------------------------------------------------------------

def _fred_latest(series_id: str, cfg: Config) -> float | None:
    """Most recent numeric observation of a FRED series."""
    if not cfg.fred.key:
        return None
    url = f"{cfg.fred.base_url}/series/observations"
    params = {
        "series_id": series_id,
        "api_key": cfg.fred.key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": "1",
    }
    try:
        resp = fetch_with_retry("GET", url, params=params)
        obs = resp.json().get("observations", []) or []
        if obs and obs[0].get("value") not in (None, ".", ""):
            return float(obs[0]["value"])
    except Exception as exc:  # noqa: BLE001
        log.warning(f"FRED series {series_id} fetch failed: {exc}")
    return None


def get_vix(cfg: Config) -> float | None:
    """Current VIX level (FRED VIXCLS — daily close)."""
    return _fred_latest("VIXCLS", cfg)


def get_treasury_yields(cfg: Config) -> dict[str, float | None]:
    """10Y and 2Y Treasury constant-maturity yields (FRED DGS10 / DGS2)."""
    return {
        "yield_10y": _fred_latest("DGS10", cfg),
        "yield_2y": _fred_latest("DGS2", cfg),
    }


# FRED release names that map to the high-impact macro events the blackout
# gate cares about (mirrors the old FMP keyword set).
_FRED_RELEASE_KEYWORDS = (
    "consumer price index",
    "employment situation",
    "producer price index",
    "gross domestic product",
    "personal income and outlays",
    "advance monthly sales for retail",
)


def _load_fomc_dates() -> list[str]:
    """FOMC meeting dates (YYYY-MM-DD) from data/fomc_dates.json.

    FOMC decisions aren't a FRED 'release', so the fixed (publicly-published)
    meeting schedule lives in a small version-controlled data file.
    """
    import json
    path = DATA_DIR / "fomc_dates.json"
    if not path.exists():
        return []
    try:
        with open(path) as f:
            data = json.load(f)
        return list(data.get("fomc_dates", data if isinstance(data, list) else []))
    except Exception as exc:  # noqa: BLE001
        log.warning(f"FOMC dates file unreadable: {exc}")
        return []


def get_economic_calendar(cfg: Config, days_ahead: int = 7) -> list[dict[str, Any]]:
    """Upcoming high-impact US macro events in the next ``days_ahead`` days.

    FRED release dates (CPI, jobs, PPI, GDP, PCE, retail) + the FOMC schedule.
    Same shape as the old FMP fetcher: ``[{date, event, impact, previous,
    estimate}]``. Returns [] (gate fails open) when FRED key is absent.
    """
    today = datetime.now(timezone.utc).date()
    horizon = today + timedelta(days=days_ahead)
    events: list[dict[str, Any]] = []

    # FOMC (from the local schedule)
    for d in _load_fomc_dates():
        try:
            dt = datetime.strptime(d, "%Y-%m-%d").date()
        except ValueError:
            continue
        if today <= dt <= horizon:
            events.append({
                "date": d, "event": "FOMC Meeting (Federal Funds Rate decision)",
                "impact": "High", "previous": None, "estimate": None,
            })

    # FRED economic releases
    if cfg.fred.key:
        url = f"{cfg.fred.base_url}/releases/dates"
        params = {
            "api_key": cfg.fred.key,
            "file_type": "json",
            "include_release_dates_with_no_data": "true",
            "sort_order": "asc",
            "limit": "1000",
        }
        try:
            resp = fetch_with_retry("GET", url, params=params)
            for entry in resp.json().get("release_dates", []) or []:
                name = entry.get("release_name", "")
                date_str = entry.get("date", "")
                if not date_str:
                    continue
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d").date()
                except ValueError:
                    continue
                if not (today <= dt <= horizon):
                    continue
                if any(kw in name.lower() for kw in _FRED_RELEASE_KEYWORDS):
                    events.append({
                        "date": date_str, "event": name,
                        "impact": "High", "previous": None, "estimate": None,
                    })
        except Exception as exc:  # noqa: BLE001
            log.warning(f"FRED economic calendar fetch failed: {exc}")

    events.sort(key=lambda e: e["date"])
    return events


# ---------------------------------------------------------------------------
# Finnhub — earnings dates, analyst recommendations, sector (per-ticker)
# ---------------------------------------------------------------------------

def get_earnings_dates(tickers: list[str], cfg: Config) -> dict[str, str | None]:
    """Next earnings date per ticker (Finnhub earnings calendar, one call).

    Returns ``{ticker: "YYYY-MM-DD" | None}``. Empty/None for all when the
    Finnhub key is absent (earnings-blackout gate fails open).
    """
    result: dict[str, str | None] = {t: None for t in tickers}
    if not cfg.finnhub.key:
        return result
    today = datetime.now(timezone.utc).date()
    url = f"{cfg.finnhub.base_url}/calendar/earnings"
    params = {
        "from": today.isoformat(),
        "to": (today + timedelta(days=60)).isoformat(),
        "token": cfg.finnhub.key,
    }
    try:
        resp = fetch_with_retry("GET", url, params=params)
        cal = resp.json().get("earningsCalendar", []) or []
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Finnhub earnings calendar fetch failed: {exc}")
        return result
    ticker_set = set(tickers)
    for entry in sorted(cal, key=lambda e: e.get("date", "")):
        sym = entry.get("symbol", "")
        if sym in ticker_set and result[sym] is None:
            result[sym] = entry.get("date")
    return result


def get_analyst_ratings(ticker: str, cfg: Config) -> dict[str, Any]:
    """Analyst recommendation trend from Finnhub (replaces FMP grades).

    Returns ``{"recent_grades": [...]}`` summarising the latest buy/hold/sell
    distribution. Price-target consensus has no free source post-FMP, so it's
    omitted (Claude still sees the recommendation mix). Empty when no key.
    """
    result: dict[str, Any] = {}
    if not cfg.finnhub.key:
        return result
    url = f"{cfg.finnhub.base_url}/stock/recommendation"
    params = {"symbol": ticker, "token": cfg.finnhub.key}
    try:
        resp = fetch_with_retry("GET", url, params=params)
        rows = resp.json() or []
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Finnhub recommendation fetch failed for {ticker}: {exc}")
        return result
    if rows and isinstance(rows, list):
        recent = rows[0]  # most recent period first
        result["recent_grades"] = [{
            "date": recent.get("period", ""),
            "strong_buy": recent.get("strongBuy", 0),
            "buy": recent.get("buy", 0),
            "hold": recent.get("hold", 0),
            "sell": recent.get("sell", 0),
            "strong_sell": recent.get("strongSell", 0),
        }]
    return result


def get_sector(ticker: str, cfg: Config) -> str:
    """Company sector/industry (Finnhub profile2). 'Unknown' when unavailable."""
    if not cfg.finnhub.key:
        return "Unknown"
    url = f"{cfg.finnhub.base_url}/stock/profile2"
    params = {"symbol": ticker, "token": cfg.finnhub.key}
    try:
        resp = fetch_with_retry("GET", url, params=params)
        data = resp.json() or {}
        return data.get("finnhubIndustry") or "Unknown"
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Finnhub sector fetch failed for {ticker}: {exc}")
    return "Unknown"
