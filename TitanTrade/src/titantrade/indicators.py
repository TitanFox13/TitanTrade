"""Technical indicator calculations from raw OHLCV data.

All indicators computed with pure Python (no pandas/numpy dependency).
Functions expect a list of OHLCV dicts sorted oldest-first.
"""

from __future__ import annotations

from typing import Any


def _closes(bars: list[dict[str, Any]]) -> list[float]:
    return [b["close"] for b in bars]


def _volumes(bars: list[dict[str, Any]]) -> list[float]:
    return [b["volume"] for b in bars]


# ---------------------------------------------------------------------------
# Simple Moving Average
# ---------------------------------------------------------------------------

def sma(values: list[float], period: int) -> float | None:
    """Return the SMA of the last `period` values, or None if insufficient data."""
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def sma_series(values: list[float], period: int) -> list[float | None]:
    """Return SMA for each point in the series."""
    result: list[float | None] = []
    for i in range(len(values)):
        if i + 1 < period:
            result.append(None)
        else:
            result.append(sum(values[i + 1 - period : i + 1]) / period)
    return result


# ---------------------------------------------------------------------------
# Exponential Moving Average
# ---------------------------------------------------------------------------

def ema_series(values: list[float], period: int) -> list[float]:
    """Compute EMA series. First value seeded with SMA."""
    if len(values) < period:
        return []
    k = 2 / (period + 1)
    result = [sum(values[:period]) / period]
    for v in values[period:]:
        result.append(v * k + result[-1] * (1 - k))
    return result


def ema(values: list[float], period: int) -> float | None:
    """Return the current (last) EMA value."""
    series = ema_series(values, period)
    return series[-1] if series else None


# ---------------------------------------------------------------------------
# RSI (Relative Strength Index) - Wilder's smoothing
# ---------------------------------------------------------------------------

def rsi(values: list[float], period: int = 14) -> float | None:
    """Compute RSI using Wilder's smoothed moving average of gains/losses."""
    if len(values) < period + 1:
        return None

    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(d, 0) for d in deltas]
    losses = [abs(min(d, 0)) for d in deltas]

    # Seed with simple average of first `period` values
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Wilder's smoothing for the rest
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# ---------------------------------------------------------------------------
# MACD (Moving Average Convergence Divergence)
# ---------------------------------------------------------------------------

def macd(
    values: list[float],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> dict[str, float | None]:
    """Return MACD line, signal line, and histogram."""
    ema_fast = ema_series(values, fast)
    ema_slow = ema_series(values, slow)

    if not ema_fast or not ema_slow:
        return {"macd_line": None, "signal_line": None, "histogram": None}

    # Align: ema_slow starts later, so trim ema_fast to match
    offset = slow - fast
    macd_line_series = [
        ema_fast[offset + i] - ema_slow[i] for i in range(len(ema_slow))
    ]

    signal_series = ema_series(macd_line_series, signal_period)

    if not signal_series:
        return {
            "macd_line": macd_line_series[-1] if macd_line_series else None,
            "signal_line": None,
            "histogram": None,
        }

    macd_val = macd_line_series[-1]
    signal_val = signal_series[-1]
    return {
        "macd_line": round(macd_val, 4),
        "signal_line": round(signal_val, 4),
        "histogram": round(macd_val - signal_val, 4),
    }


# ---------------------------------------------------------------------------
# Bollinger Bands
# ---------------------------------------------------------------------------

def bollinger_bands(
    values: list[float], period: int = 20, num_std: float = 2.0
) -> dict[str, float | None]:
    """Return upper, middle (SMA), and lower Bollinger Bands."""
    if len(values) < period:
        return {"upper": None, "middle": None, "lower": None}

    window = values[-period:]
    middle = sum(window) / period
    variance = sum((x - middle) ** 2 for x in window) / period
    std_dev = variance ** 0.5

    return {
        "upper": round(middle + num_std * std_dev, 4),
        "middle": round(middle, 4),
        "lower": round(middle - num_std * std_dev, 4),
    }


# ---------------------------------------------------------------------------
# ATR (Average True Range) - Wilder's smoothing
# ---------------------------------------------------------------------------

def atr(bars: list[dict[str, Any]], period: int = 14) -> float | None:
    """Compute ATR using Wilder's smoothing. Needs at least period+1 bars."""
    if len(bars) < period + 1:
        return None

    true_ranges: list[float] = []
    for i in range(1, len(bars)):
        high = bars[i]["high"]
        low = bars[i]["low"]
        prev_close = bars[i - 1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)

    # Seed with simple average
    atr_val = sum(true_ranges[:period]) / period

    # Wilder's smoothing
    for i in range(period, len(true_ranges)):
        atr_val = (atr_val * (period - 1) + true_ranges[i]) / period

    return round(atr_val, 4)


# ---------------------------------------------------------------------------
# Volume analysis
# ---------------------------------------------------------------------------

def volume_trend(bars: list[dict[str, Any]]) -> dict[str, float | None]:
    """Compare recent volume to longer-term average."""
    vols = _volumes(bars)
    avg_5 = sma(vols, 5)
    avg_20 = sma(vols, 20)

    ratio = None
    if avg_5 is not None and avg_20 is not None and avg_20 > 0:
        ratio = round(avg_5 / avg_20, 4)

    return {
        "avg_volume_5d": round(avg_5) if avg_5 else None,
        "avg_volume_20d": round(avg_20) if avg_20 else None,
        "volume_ratio_5d_20d": ratio,  # >1 = increasing volume
    }


# ---------------------------------------------------------------------------
# Price position analysis
# ---------------------------------------------------------------------------

def price_vs_sma(
    bars: list[dict[str, Any]],
) -> dict[str, Any]:
    """Where is the current price relative to key SMAs?"""
    closes = _closes(bars)
    current = closes[-1] if closes else None

    sma_20 = sma(closes, 20)
    sma_50 = sma(closes, 50)
    sma_200 = sma(closes, 200)

    def pct_from(price: float | None, ref: float | None) -> float | None:
        if price is None or ref is None or ref == 0:
            return None
        return round((price - ref) / ref * 100, 2)

    return {
        "current_price": current,
        "sma_20": round(sma_20, 2) if sma_20 else None,
        "sma_50": round(sma_50, 2) if sma_50 else None,
        "sma_200": round(sma_200, 2) if sma_200 else None,
        "pct_from_sma_20": pct_from(current, sma_20),
        "pct_from_sma_50": pct_from(current, sma_50),
        "pct_from_sma_200": pct_from(current, sma_200),
        "above_sma_50": current > sma_50 if current and sma_50 else None,
        "above_sma_200": current > sma_200 if current and sma_200 else None,
        "golden_cross": sma_50 > sma_200 if sma_50 and sma_200 else None,
    }


# ---------------------------------------------------------------------------
# Relative strength vs benchmark
# ---------------------------------------------------------------------------

def relative_strength(
    stock_bars: list[dict[str, Any]],
    benchmark_bars: list[dict[str, Any]],
    periods: list[int] | None = None,
) -> dict[str, float | None]:
    """Compute relative strength: stock return minus benchmark return.

    Positive RS means the stock is outperforming the benchmark.
    """
    if periods is None:
        periods = [5, 20, 60]

    stock_closes = _closes(stock_bars)
    bench_closes = _closes(benchmark_bars)

    result: dict[str, float | None] = {}
    for p in periods:
        if len(stock_closes) <= p or len(bench_closes) <= p:
            result[f"rs_{p}d"] = None
            continue
        stock_ret = (stock_closes[-1] - stock_closes[-(p + 1)]) / stock_closes[-(p + 1)] * 100
        bench_ret = (bench_closes[-1] - bench_closes[-(p + 1)]) / bench_closes[-(p + 1)] * 100
        result[f"rs_{p}d"] = round(stock_ret - bench_ret, 2)

    return result


# ---------------------------------------------------------------------------
# Correlation
# ---------------------------------------------------------------------------

def correlation(
    closes_a: list[float],
    closes_b: list[float],
    period: int = 60,
) -> float | None:
    """Pearson correlation between two close price series over the last N days."""
    a = closes_a[-period:]
    b = closes_b[-period:]
    n = min(len(a), len(b))
    if n < 20:
        return None
    a, b = a[-n:], b[-n:]

    # Convert to returns
    ret_a = [(a[i] - a[i - 1]) / a[i - 1] for i in range(1, n) if a[i - 1] != 0]
    ret_b = [(b[i] - b[i - 1]) / b[i - 1] for i in range(1, n) if b[i - 1] != 0]
    n = min(len(ret_a), len(ret_b))
    if n < 10:
        return None
    ret_a, ret_b = ret_a[:n], ret_b[:n]

    mean_a = sum(ret_a) / n
    mean_b = sum(ret_b) / n

    cov = sum((ret_a[i] - mean_a) * (ret_b[i] - mean_b) for i in range(n)) / n
    std_a = (sum((x - mean_a) ** 2 for x in ret_a) / n) ** 0.5
    std_b = (sum((x - mean_b) ** 2 for x in ret_b) / n) ** 0.5

    if std_a == 0 or std_b == 0:
        return None

    return round(cov / (std_a * std_b), 3)


# ---------------------------------------------------------------------------
# Master function: compute all indicators for a stock
# ---------------------------------------------------------------------------

def compute_all_indicators(bars: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute the full indicator suite from OHLCV bars (oldest first).

    Requires at least 200 bars for full coverage (200-day SMA).
    Works with fewer bars but some indicators will be None.
    """
    closes = _closes(bars)

    return {
        "rsi_14": round(rsi(closes, 14), 2) if rsi(closes, 14) is not None else None,
        "macd": macd(closes),
        "bollinger": bollinger_bands(closes),
        "atr_14": atr(bars, 14),
        "price_vs_sma": price_vs_sma(bars),
        "volume": volume_trend(bars),
    }
