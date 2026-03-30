"""Market-wide context: SPY/QQQ trend, VIX, 10Y Treasury, regime classification.

Provides the macro backdrop that individual stock analysis needs.
Going BULLISH on a tech stock while VIX is at 35 and SPY is in a downtrend
is fighting the market - this module prevents that.

Sector mapping is dynamic: fetched from FMP for any ticker and cached locally.
This means the watchlist can be changed freely without code changes.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from titantrade.config import Config, STATE_DIR
from titantrade.indicators import atr, compute_all_indicators, rsi, sma
from titantrade.logger import get_logger
from titantrade.retry import fetch_with_retry

log = get_logger("market_context")

# Tickers we track for macro context
MARKET_TICKERS = {
    "spy": "SPY",       # S&P 500 ETF
    "qqq": "QQQ",       # Nasdaq 100 ETF
    "dia": "DIA",       # Dow Jones ETF
    "iwm": "IWM",       # Russell 2000 (small caps)
    "vix": "^VIX",      # CBOE Volatility Index
}

# Sector ETFs for rotation analysis
SECTOR_ETFS = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financials": "XLF",
    "Consumer Discretionary": "XLY",
    "Communication Services": "XLC",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Consumer Staples": "XLP",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Materials": "XLB",
}

# In-memory cache (populated on first access from FMP + local file)
_sector_cache: dict[str, str] = {}


def _sector_cache_path():
    return STATE_DIR / "sector_cache.json"


def _load_sector_cache() -> dict[str, str]:
    """Load sector cache from disk."""
    path = _sector_cache_path()
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def _save_sector_cache(cache: dict[str, str]) -> None:
    """Save sector cache to disk."""
    with open(_sector_cache_path(), "w") as f:
        json.dump(cache, f, indent=2)


def _fetch_sector_from_fmp(ticker: str, cfg: Config) -> str:
    """Look up a stock's sector from FMP company profile. Returns sector name."""
    url = f"{cfg.fmp.base_url}/profile/{ticker}"
    params = {"apikey": cfg.fmp.key}
    try:
        resp = fetch_with_retry("GET", url, params=params)
        data = resp.json()
        if data and isinstance(data, list) and data[0].get("sector"):
            return data[0]["sector"]
    except Exception as exc:
        log.warning(f"Failed to fetch sector for {ticker}: {exc}")
    return "Unknown"


def load_stock_sectors(tickers: list[str], cfg: Config) -> dict[str, str]:
    """Load sectors for all tickers, fetching from FMP for any unknown ones.

    Results are cached in state/sector_cache.json so we only hit FMP once per ticker.
    """
    global _sector_cache

    if not _sector_cache:
        _sector_cache = _load_sector_cache()

    missing = [t for t in tickers if t not in _sector_cache]

    if missing:
        log.info(f"Fetching sectors for {len(missing)} new tickers: {missing}")
        for ticker in missing:
            _sector_cache[ticker] = _fetch_sector_from_fmp(ticker, cfg)
        _save_sector_cache(_sector_cache)

    return {t: _sector_cache.get(t, "Unknown") for t in tickers}


def get_stock_sector(ticker: str) -> str:
    """Return the cached sector for a stock. Returns 'Unknown' if not yet loaded."""
    return _sector_cache.get(ticker, "Unknown")


def _fetch_bars(ticker: str, cfg: Config, days: int = 250) -> list[dict[str, Any]]:
    """Fetch historical bars from FMP, oldest first."""
    today = datetime.now(timezone.utc).date()
    from_date = today - timedelta(days=int(days * 1.5))  # pad for weekends/holidays

    url = f"{cfg.fmp.base_url}/stable/historical-price-eod-full/{ticker}"
    params = {
        "from": from_date.isoformat(),
        "to": today.isoformat(),
        "apikey": cfg.fmp.key,
    }

    resp = fetch_with_retry("GET", url, params=params)
    data = resp.json()
    historical = data.get("historical", [])

    # FMP returns newest-first, we need oldest-first
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


def _fetch_vix_level(cfg: Config) -> float | None:
    """Fetch the current VIX level."""
    url = f"{cfg.fmp.base_url}/quote/%5EVIX"
    params = {"apikey": cfg.fmp.key}
    try:
        resp = fetch_with_retry("GET", url, params=params)
        data = resp.json()
        if data and isinstance(data, list):
            return data[0].get("price")
    except Exception as exc:
        log.warning(f"Failed to fetch VIX: {exc}")
    return None


def _fetch_treasury_yield(cfg: Config) -> dict[str, float | None]:
    """Fetch 10Y and 2Y Treasury yields from FMP."""
    url = f"{cfg.fmp.base_url}/treasury"
    params = {"apikey": cfg.fmp.key}
    result: dict[str, float | None] = {"yield_10y": None, "yield_2y": None}
    try:
        resp = fetch_with_retry("GET", url, params=params)
        data = resp.json()
        if data and isinstance(data, list):
            entry = data[0]
            result["yield_10y"] = entry.get("year10")
            result["yield_2y"] = entry.get("year2")
    except Exception as exc:
        log.warning(f"Failed to fetch treasury yields: {exc}")
    return result


def _compute_return(bars: list[dict[str, Any]], days: int) -> float | None:
    """Percentage return over the last N trading days."""
    if len(bars) < days + 1:
        return None
    old = bars[-(days + 1)]["close"]
    new = bars[-1]["close"]
    if old == 0:
        return None
    return round((new - old) / old * 100, 2)


def _classify_vix(vix: float | None) -> str:
    """Classify VIX level into a regime label."""
    if vix is None:
        return "unknown"
    if vix < 15:
        return "low_volatility"
    if vix < 20:
        return "normal"
    if vix < 25:
        return "elevated"
    if vix < 35:
        return "high"
    return "extreme_fear"


def _classify_market_regime(
    spy_indicators: dict[str, Any],
    vix_level: float | None,
) -> str:
    """Classify overall market regime.

    Returns: strong_bullish, bullish, neutral, bearish, strong_bearish, crisis
    """
    price_sma = spy_indicators.get("price_vs_sma", {})
    above_50 = price_sma.get("above_sma_50")
    above_200 = price_sma.get("above_sma_200")
    golden_cross = price_sma.get("golden_cross")
    spy_rsi = spy_indicators.get("rsi_14")

    if vix_level is not None and vix_level >= 35:
        return "crisis"

    if above_50 and above_200 and golden_cross:
        if spy_rsi and spy_rsi > 60:
            return "strong_bullish"
        return "bullish"

    if not above_50 and not above_200:
        if spy_rsi and spy_rsi < 40:
            return "strong_bearish"
        return "bearish"

    return "neutral"


def fetch_sector_performance(cfg: Config) -> dict[str, float | None]:
    """Fetch 5-day returns for each sector ETF to detect rotation."""
    result: dict[str, float | None] = {}
    for sector, etf in SECTOR_ETFS.items():
        try:
            bars = _fetch_bars(etf, cfg, days=10)
            result[sector] = _compute_return(bars, 5)
        except Exception as exc:
            log.warning(f"Failed to fetch sector {sector} ({etf}): {exc}")
            result[sector] = None
    return result


def build_market_context(cfg: Config) -> dict[str, Any]:
    """Build the full market context bundle.

    This is included in the data sent to Claude so it doesn't analyze
    stocks in a vacuum.
    """
    log.info("Building market context")

    # Fetch SPY data with full indicator suite
    spy_bars = _fetch_bars("SPY", cfg, days=250)
    qqq_bars = _fetch_bars("QQQ", cfg, days=250)

    spy_indicators = compute_all_indicators(spy_bars) if len(spy_bars) > 20 else {}
    qqq_indicators = compute_all_indicators(qqq_bars) if len(qqq_bars) > 20 else {}

    vix_level = _fetch_vix_level(cfg)
    treasury = _fetch_treasury_yield(cfg)

    regime = _classify_market_regime(spy_indicators, vix_level)

    # Sector performance for rotation detection
    sector_perf = fetch_sector_performance(cfg)

    # Sort sectors by performance to show flow direction
    sorted_sectors = sorted(
        [(k, v) for k, v in sector_perf.items() if v is not None],
        key=lambda x: x[1],
        reverse=True,
    )

    context = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market_regime": regime,
        "vix": {
            "level": vix_level,
            "classification": _classify_vix(vix_level),
        },
        "treasury": treasury,
        "spy": {
            "return_1d": _compute_return(spy_bars, 1),
            "return_5d": _compute_return(spy_bars, 5),
            "return_20d": _compute_return(spy_bars, 20),
            "indicators": spy_indicators,
        },
        "qqq": {
            "return_1d": _compute_return(qqq_bars, 1),
            "return_5d": _compute_return(qqq_bars, 5),
            "return_20d": _compute_return(qqq_bars, 20),
            "indicators": qqq_indicators,
        },
        "sector_rotation": {
            "performance_5d": sector_perf,
            "strongest": sorted_sectors[:3] if sorted_sectors else [],
            "weakest": sorted_sectors[-3:] if sorted_sectors else [],
        },
    }

    # Include raw bars for downstream relative strength / correlation computation
    # These are stripped before saving to state
    context["_spy_bars"] = spy_bars

    log.info(f"Market regime: {regime} | VIX: {vix_level} | SPY 5d: {context['spy']['return_5d']}%")
    return context
