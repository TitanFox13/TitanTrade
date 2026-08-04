"""Trend-regime classification and entry-price selection.

Pure functions over the data bundle / thesis dicts — no I/O, no broker.
Extracted from executor.py (behavior-preserving).
"""

from __future__ import annotations

from typing import Any


def compute_trend_regime(
    ticker: str,
    data_bundle: dict[str, Any],
    current_price: float | None = None,
) -> str:
    """Classify a ticker's trend regime from its technical indicators.

    Returns one of:
      "strong_up" — golden cross, price >2% above SMA-50, above SMA-20,
                    RSI not in exhausted territory (<75). Use a near-market
                    entry: don't wait for a dip that isn't coming.
      "up"        — above SMA-50 but lacks the strong-up criteria.
                    Use a small-buffer-above-current breakout entry.
      "range"     — neither clearly trending up nor down (also where we
                    downgrade overbought-but-trending names — buying RSI 80
                    extensions is how you become exit liquidity).
      "down"      — below SMA-50 with negative momentum. Skip entry.

    The whole point: in a rising market we kept missing entries because the
    limit-below-current strategy never filled. Trend-aware sizing lets us
    match the entry method to the actual price action.
    """
    stock = data_bundle.get("stocks", {}).get(ticker, {})
    tech = stock.get("technical_indicators", {}) or {}
    pvs = tech.get("price_vs_sma", {}) or {}

    above_50 = pvs.get("above_sma_50")
    above_200 = pvs.get("above_sma_200")
    golden = pvs.get("golden_cross")
    pct_from_50 = pvs.get("pct_from_sma_50")
    sma_20 = pvs.get("sma_20")
    rsi = tech.get("rsi_14")

    # Overbought guard: even in a screaming uptrend, RSI > 75 means we'd be
    # buying the spike. Downgrade to "range" — let the thesis-target limit
    # wait for the inevitable pullback. (RSI < 25 in downtrend = catching
    # falling knives; also already caught by the "down" branch.)
    is_overbought = rsi is not None and rsi > 75

    # Strong uptrend: above SMA-50 with cushion, golden cross, price > SMA-20,
    # NOT overbought. When all four line up the path of least resistance is up.
    if (
        above_50 is True
        and golden is True
        and pct_from_50 is not None and pct_from_50 > 2.0
        and current_price is not None and sma_20 is not None
        and current_price > sma_20
        and not is_overbought
    ):
        return "strong_up"

    # Plain uptrend: above SMA-50 (and not overbought).
    if above_50 is True and (pct_from_50 or 0) > 0 and not is_overbought:
        return "up"

    # Downtrend: below SMA-50 AND below SMA-200 AND noticeably negative
    # from the SMA-50. Skip entry — we're not bottom-fishing.
    if (
        above_50 is False
        and above_200 is False
        and (pct_from_50 or 0) < -2.0
    ):
        return "down"

    return "range"


def _choose_entry_price(
    thesis: dict[str, Any],
    current_price: float | None,
    regime: str,
    confidence: float,
) -> float:
    """Pick the entry limit price based on trend regime + confidence.

    The original strategy always used the thesis ``target_entry_price``, which
    is a dip-buy level set at thesis-generation time (often hours or days ago).
    In a rising market this guarantees the order expires unfilled.

    New rules (when current price is available):
      - confidence >= 0.80 OR strong_up regime → buy near-market
        (current_price * 1.003 — cross the spread for a near-immediate fill)
      - up regime → buy at current * 1.001 (small breakout buffer)
      - range / no current price → use thesis target (dip-buy)
      - down regime is filtered out by caller before this is reached

    Always returns a price >= the thesis stop_loss_price; callers should
    still validate bracket math (stop < entry < tp).
    """
    target = float(thesis.get("target_entry_price") or 0)
    if not current_price:
        return target

    if confidence >= 0.80 or regime == "strong_up":
        return round(current_price * 1.003, 2)
    if regime == "up":
        return round(current_price * 1.001, 2)
    # Range: keep the thesis target, but cap at current_price so we don't
    # accidentally pay above market if the thesis is stale-low.
    return round(min(target, current_price), 2) if target else round(current_price, 2)


# ---------------------------------------------------------------------------
# Data-bundle accessors (shared by the entry paths and executor)
# ---------------------------------------------------------------------------

def stock_atr(ticker: str, data_bundle: dict[str, Any]) -> float | None:
    """ATR-14 for ``ticker`` from the data bundle, or None."""
    return data_bundle.get("stocks", {}).get(ticker, {}).get("atr_14")


def earnings_blocked(ticker: str, data_bundle: dict[str, Any]) -> bool:
    """Whether ``ticker`` is inside its earnings blackout per the data bundle."""
    return (
        data_bundle.get("stocks", {}).get(ticker, {})
        .get("earnings", {}).get("is_blocked", False)
    )


def vix_level(data_bundle: dict[str, Any]) -> float | None:
    """Current VIX level from the data bundle's market context, or None."""
    return data_bundle.get("market_context", {}).get("vix", {}).get("level")


# ---------------------------------------------------------------------------
# Entry-level adaptation + bracket validation (shared by new-entry & resubmit)
# ---------------------------------------------------------------------------

def adapt_entry_levels(
    thesis: dict[str, Any],
    entry_price: float,
    stop_price: float,
    take_profit_price: float | None,
    current_price: float | None,
    regime: str,
    confidence: float,
) -> tuple[float, float, float | None, float | None]:
    """Adapt the entry to the current price/regime and walk stop + TP by the
    same delta (measured from the thesis target) to preserve risk:reward.

    Returns ``(entry, stop, take_profit, new_entry)`` where ``new_entry`` is the
    adapted price if adaptation occurred (so the caller can log it) or ``None``
    if levels are unchanged. Behavior-identical to the inline logic that used to
    live in both ``_handle_bullish_entry`` and ``resubmit_expired_brackets``.
    """
    new_entry = _choose_entry_price(thesis, current_price, regime, confidence)
    if not new_entry or new_entry == entry_price:
        return entry_price, stop_price, take_profit_price, None
    entry_price = new_entry
    original_target = thesis.get("target_entry_price")
    if original_target and original_target > 0 and entry_price != original_target:
        delta = entry_price - original_target  # negative if walking down
        stop_price = round(stop_price + delta, 2)
        if take_profit_price:
            take_profit_price = round(take_profit_price + delta, 2)
    return entry_price, stop_price, take_profit_price, new_entry


def bracket_levels_invalid(
    entry_price: float | None,
    stop_price: float | None,
    take_profit_price: float | None,
) -> str | None:
    """Return a human-readable reason a (entry, stop, tp) triple is an invalid
    NEW bracket, or None if valid. Alpaca rejects stop >= entry (HTTP 422); a
    stop above entry means the thesis is for *managing* a held position, not
    opening one. Used by both entry paths."""
    if stop_price is not None and entry_price is not None and stop_price >= entry_price - 0.01:
        return (
            f"stop ${stop_price:.2f} >= entry ${entry_price:.2f} "
            f"(thesis is for managing an existing position, not a new entry)"
        )
    if take_profit_price is not None and stop_price is not None and take_profit_price <= stop_price:
        return f"take_profit ${take_profit_price:.2f} <= stop ${stop_price:.2f} (bracket math invalid)"
    return None


# A stop closer than this (% of entry) is inside normal intraday noise and
# gets tagged out within minutes of the fill: production URI entered at
# $1084.25 with a $1081.25 stop (0.28%) and was stopped out 27 minutes later
# (2026-07-31). Typical thesis stops run 3-5%, so 1.5% only catches the
# degenerate artifacts — usually an ADJUST-review thesis whose tightened
# stop was reused for a fresh entry. Deliberately a flat floor, not
# ATR-scaled: 1x ATR exceeds the normal stop distance on high-vol names and
# would start refusing legitimate entries.
MIN_STOP_DISTANCE_PCT = 1.5


def stop_too_tight(entry_price: float | None, stop_price: float | None) -> str | None:
    """Return a reason string when the stop sits within noise distance of the
    entry (< ``MIN_STOP_DISTANCE_PCT``% below it), or None if acceptable.

    Only fires for a stop strictly *below* the entry — a stop at/above entry
    is invalid bracket math and is ``bracket_levels_invalid``'s job to report.
    """
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
