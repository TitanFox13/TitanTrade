"""Entry pricing and bracket validation (pure).

The plan carries levels computed from the last close; at order time the
executor re-anchors them to the live price: a near-market limit entry (so the
order fills, as the backtest's next-close fill assumes) with the stop and the
target as fixed percentages of that entry.
"""
from __future__ import annotations

from typing import Any

from titantrade.config import Config

# Cross the spread for a near-immediate fill.
NEAR_MARKET_BUFFER = 0.003

# A stop closer than this (% of entry) is inside normal intraday noise and
# gets tagged out within minutes of the fill (production URI 2026-07-31:
# entered $1084.25 with a $1081.25 stop, stopped 27 minutes later).
MIN_STOP_DISTANCE_PCT = 1.5


def near_market_entry(current_price: float | None) -> float | None:
    """Limit price just above the live mark, or None without a mark."""
    if not current_price or current_price <= 0:
        return None
    return round(current_price * (1 + NEAR_MARKET_BUFFER), 2)


def entry_levels(
    cfg: Config, current_price: float | None, fallback_entry: float | None = None,
) -> tuple[float | None, float | None, float | None]:
    """``(entry, stop, target)`` anchored to the live price (or the plan's
    entry when no live price is available). Stop and target are the
    configured percentages of the entry."""
    entry = near_market_entry(current_price) or (round(float(fallback_entry), 2) if fallback_entry else None)
    if not entry:
        return None, None, None
    return entry, round(entry * (1 - cfg.trading.stop_pct), 2), round(entry * (1 + cfg.trading.tp_pct), 2)


def bracket_levels_invalid(
    entry_price: float | None,
    stop_price: float | None,
    take_profit_price: float | None,
) -> str | None:
    """Reason an (entry, stop, tp) triple is an invalid bracket, or None.
    Alpaca rejects stop >= entry (HTTP 422)."""
    if stop_price is not None and entry_price is not None and stop_price >= entry_price - 0.01:
        return f"stop ${stop_price:.2f} >= entry ${entry_price:.2f}"
    if take_profit_price is not None and stop_price is not None and take_profit_price <= stop_price:
        return f"take_profit ${take_profit_price:.2f} <= stop ${stop_price:.2f} (bracket math invalid)"
    return None


def stop_too_tight(entry_price: float | None, stop_price: float | None) -> str | None:
    """Reason when the stop sits within noise distance of the entry, else None."""
    if not entry_price or not stop_price:
        return None
    distance_pct = (entry_price - stop_price) / entry_price * 100
    if distance_pct <= 0:
        return None
    if distance_pct < MIN_STOP_DISTANCE_PCT:
        return (
            f"stop ${stop_price:.2f} is only {distance_pct:.2f}% below entry "
            f"${entry_price:.2f} (< {MIN_STOP_DISTANCE_PCT}% floor) — "
            f"noise-level stop would tag out immediately"
        )
    return None


# --- Data-bundle accessors ---------------------------------------------------

def stock_atr(ticker: str, data_bundle: dict[str, Any]) -> float | None:
    """ATR-14 for ``ticker`` from the data bundle, or None."""
    return data_bundle.get("stocks", {}).get(ticker, {}).get("atr_14")


def earnings_blocked(ticker: str, data_bundle: dict[str, Any]) -> bool:
    """Whether ``ticker`` is inside its earnings blackout per the data bundle."""
    return bool(
        data_bundle.get("stocks", {}).get(ticker, {})
        .get("earnings", {}).get("is_blocked", False)
    )
