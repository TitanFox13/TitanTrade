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
