"""Mechanical strategy signals (Decision 061).

Pure functions over price series. The same code serves the live executor
(through ``signal_inputs`` baked into the data bundle) and the backtester, so
what is backtested is exactly what trades.

Rules:
  entry     close >= ``dip_pct`` below its ``lookback``-day high AND above its
            ``trend_sma``-day SMA ("buy the dip in an uptrend")
  insurance exposure scaled to ``scale`` only when SPY is below its SMA AND the
            share of sector ETFs above their SMA is below ``breadth_threshold``
            (two-signal confirmation — the cheapest insurance in the decade test)
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable


def sma(values: list[float], n: int) -> float | None:
    """Simple moving average of the last ``n`` values, None with fewer."""
    if n <= 0 or len(values) < n:
        return None
    window = values[-n:]
    return sum(window) / n


def rolling_high(values: list[float], n: int) -> float | None:
    """Highest of the last ``n`` values; needs at least half a window."""
    if n <= 0 or len(values) < max(1, n // 2):
        return None
    return max(values[-n:])


def evaluate_dip(
    close: float | None,
    high: float | None,
    trend: float | None,
    *,
    dip_pct: float,
) -> dict[str, Any]:
    """Dip-in-uptrend state from the three inputs the rule needs."""
    dip = (high - close) / high if close and high and high > 0 else None
    above = (close > trend) if (close is not None and trend) else None
    return {
        "close": close,
        "high": high,
        "sma_trend": trend,
        "dip_pct": round(dip, 4) if dip is not None else None,
        "above_trend": above,
        "signal": bool(dip is not None and dip >= dip_pct and above is True),
    }


def dip_state(
    closes: list[float], *, dip_pct: float, lookback: int, trend_sma: int,
) -> dict[str, Any]:
    """``evaluate_dip`` over a close series (newest last)."""
    close = closes[-1] if closes else None
    return evaluate_dip(
        close, rolling_high(closes, lookback), sma(closes, trend_sma), dip_pct=dip_pct,
    )


def above_sma_flags(series_by_symbol: dict[str, list[float]], n: int) -> dict[str, bool | None]:
    """Per symbol: close above its ``n``-day SMA (None when too short)."""
    out: dict[str, bool | None] = {}
    for sym, closes in series_by_symbol.items():
        s = sma(closes, n)
        out[sym] = (closes[-1] > s) if (closes and s) else None
    return out


def breadth(flags: Iterable[bool | None]) -> float | None:
    """Share of True among the non-None flags; None when nothing is known."""
    known = [f for f in flags if f is not None]
    return (sum(1 for f in known if f) / len(known)) if known else None


def insurance_state(
    spy_above_sma: bool | None,
    sector_breadth: float | None,
    *,
    breadth_threshold: float,
    scale: float,
) -> dict[str, Any]:
    """Two-signal de-risk: both must say "off" to cut exposure. Fails open
    (full exposure) when either input is unknown."""
    risk_off = (
        spy_above_sma is False
        and sector_breadth is not None
        and sector_breadth < breadth_threshold
    )
    return {
        "risk_off": risk_off,
        "spy_above_sma": spy_above_sma,
        "sector_breadth": round(sector_breadth, 3) if sector_breadth is not None else None,
        "exposure_scale": scale if risk_off else 1.0,
    }


def shock_state(
    closes: list[float], *, drop_pct: float, lookback: int, hold: int, scale: float,
) -> dict[str, Any]:
    """Fast de-risk (Decision 068): the market fell ``drop_pct`` over
    ``lookback`` sessions on one of the last ``hold`` sessions → exposure ×
    ``scale`` until ``hold`` sessions after the most recent such drop. Read
    off the close series each run (no state file). Fails open when the series
    is too short."""
    n = len(closes)
    age: int | None = None
    worst: float | None = None
    for k in range(min(hold, n)):
        i = n - 1 - k
        if i - lookback < 0:
            break
        base = closes[i - lookback]
        if not base:
            continue
        r = closes[i] / base - 1
        worst = r if worst is None else min(worst, r)
        if r <= -drop_pct and age is None:
            age = k
    active = age is not None
    return {
        "active": active,
        "sessions_left": (hold - age) if active else 0,
        "worst_drop": round(worst, 4) if worst is not None else None,
        "exposure_scale": scale if active else 1.0,
        "drop_pct": drop_pct,
        "lookback_days": lookback,
        "hold_days": hold,
    }


def rank_dips(states: dict[str, dict[str, Any]]) -> list[str]:
    """Tickers whose dip signal is on, deepest dip first."""
    on = [(t, s) for t, s in states.items() if s.get("signal")]
    on.sort(key=lambda ts: -(ts[1].get("dip_pct") or 0.0))
    return [t for t, _ in on]


def trading_days_between(start: str | None, end: datetime | None = None) -> int:
    """Weekdays from ``start`` (ISO timestamp or date) to ``end`` (UTC now).
    Holidays are not subtracted — a one-day error on a 40-day hold is noise."""
    if not start:
        return 0
    try:
        d0 = date.fromisoformat(str(start)[:10])
    except ValueError:
        return 0
    d1 = (end or datetime.now(timezone.utc)).date()
    if d1 <= d0:
        return 0
    days = 0
    cur = d0
    while cur < d1:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            days += 1
    return days
