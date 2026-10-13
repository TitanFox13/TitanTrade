"""ATR and pairwise correlation — the two indicators the live strategy uses
(Decision 063 trimmed the RSI/MACD/Bollinger suite; the full module is in legacy/)."""

from __future__ import annotations

from typing import Any

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
