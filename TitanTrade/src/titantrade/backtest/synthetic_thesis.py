"""Generate synthetic thesis from technical indicators (no LLM calls).

These heuristic rules approximate Claude's analysis for backtesting purposes.
They intentionally produce different signal timing than the real LLM — the
backtest validates risk management and execution rules, not the alpha source.
"""

from __future__ import annotations

from typing import Any

from titantrade.indicators import (
    atr as compute_atr,
    compute_all_indicators,
    sma,
)


def generate_synthetic_thesis(
    ticker: str,
    bars: list[dict[str, Any]],
    market_bars: list[dict[str, Any]] | None = None,
    sector: str = "Unknown",
) -> dict[str, Any]:
    """Generate a thesis from indicator heuristics. Zero API calls.

    Returns a thesis dict compatible with the real weekly_thesis schema.
    """
    if len(bars) < 20:
        return _neutral(ticker, sector, "Insufficient data")

    closes = [b["close"] for b in bars]
    current = closes[-1]
    indicators = compute_all_indicators(bars)

    rsi_val = indicators.get("rsi_14")
    macd_data = indicators.get("macd", {})
    histogram = macd_data.get("histogram")
    boll = indicators.get("bollinger", {})
    pvs = indicators.get("price_vs_sma", {})
    vol = indicators.get("volume", {})

    above_50 = pvs.get("above_sma_50")
    above_200 = pvs.get("above_sma_200")
    golden_cross = pvs.get("golden_cross")
    sma_200 = pvs.get("sma_200")
    vol_ratio = vol.get("volume_ratio_5d_20d")

    # Check market regime (optional)
    market_bearish = False
    if market_bars and len(market_bars) >= 50:
        spy_closes = [b["close"] for b in market_bars]
        spy_sma50 = sma(spy_closes, 50)
        if spy_sma50 and spy_closes[-1] < spy_sma50:
            market_bearish = True

    # --- Heuristic rules (ordered by priority) ---

    # Mean reversion: RSI deeply oversold near 200-SMA
    if rsi_val is not None and rsi_val < 30 and sma_200 and abs(current - sma_200) / sma_200 < 0.03:
        return _bullish(
            ticker, sector, current, confidence=0.68,
            horizon="short_term",
            stop_pct=0.04, tp_rr=2.0,
            reasoning=f"Mean reversion: RSI {rsi_val:.0f}, price near 200-SMA ${sma_200:.2f}",
            bars=bars,
        )

    # RSI extremely oversold
    if rsi_val is not None and rsi_val < 25 and not market_bearish:
        return _bullish(
            ticker, sector, current, confidence=0.65,
            horizon="short_term",
            stop_pct=0.05, tp_rr=2.0,
            reasoning=f"Extreme oversold: RSI {rsi_val:.0f}",
            bars=bars,
        )

    # Golden cross with momentum
    if golden_cross and above_50 and above_200 and histogram and histogram > 0:
        return _bullish(
            ticker, sector, current, confidence=0.75,
            horizon="medium_term",
            stop_pct=0.05, tp_rr=2.5,
            reasoning="Golden cross + MACD positive + above both SMAs",
            bars=bars,
        )

    # MACD bullish crossover with trend support
    if histogram and histogram > 0 and above_50 and rsi_val and 40 < rsi_val < 65:
        return _bullish(
            ticker, sector, current, confidence=0.72,
            horizon="short_term",
            stop_pct=0.04, tp_rr=2.0,
            reasoning=f"MACD bullish crossover, RSI {rsi_val:.0f}, above 50-SMA",
            bars=bars,
        )

    # Bollinger breakout with volume confirmation
    upper = boll.get("upper")
    if upper and current > upper and vol_ratio and vol_ratio > 1.3:
        return _bullish(
            ticker, sector, current, confidence=0.68,
            horizon="short_term",
            stop_pct=0.04, tp_rr=1.5,
            reasoning="Bollinger breakout with volume confirmation",
            bars=bars,
        )

    # Death cross or bearish trend
    if not above_50 and not above_200 and rsi_val and rsi_val < 40:
        return _neutral(ticker, sector, "Bearish trend: below both SMAs, weak RSI")

    # RSI overbought
    if rsi_val and rsi_val > 70:
        return _neutral(ticker, sector, f"Overbought: RSI {rsi_val:.0f}")

    return _neutral(ticker, sector, "No clear setup")


def _bullish(
    ticker: str, sector: str, current: float,
    confidence: float, horizon: str,
    stop_pct: float, tp_rr: float,
    reasoning: str,
    bars: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a BULLISH thesis. When bars are provided, the stop is the LARGER
    of stop_pct or 2.5x ATR — matching the new strategy guidance to Claude
    that stops < 1.5x ATR get noise-stopped. The old fixed-% stop is what
    produced 74% stop-out rate in the v2 backtest.
    """
    entry = round(current * 0.995, 2)

    # ATR-aware stop: take the LARGER of fixed-pct or 2.5x ATR below entry.
    pct_stop = entry * (1 - stop_pct)
    atr_stop = pct_stop
    if bars and len(bars) >= 15:
        a = compute_atr(bars[-30:])
        if a and a > 0:
            atr_stop = entry - 2.5 * a
    stop = round(min(pct_stop, atr_stop), 2)  # min => further BELOW entry => wider stop
    risk = entry - stop
    tp = round(entry + risk * tp_rr, 2)

    return {
        "ticker": ticker,
        "sector": sector,
        "thesis": "BULLISH",
        "confidence": confidence,
        "hold_horizon": horizon,
        "review_action": "NEW",
        "target_entry_price": entry,
        "stop_loss_price": stop,
        "take_profit_price": tp,
        "thesis_breach_condition": "Technical breakdown below stop level",
        "key_technical_levels": {},
        "reasoning": reasoning,
    }


def _neutral(ticker: str, sector: str, reasoning: str) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "sector": sector,
        "thesis": "NEUTRAL",
        "confidence": 0.5,
        "hold_horizon": "short_term",
        "review_action": "NEW",
        "target_entry_price": None,
        "stop_loss_price": None,
        "take_profit_price": None,
        "thesis_breach_condition": "",
        "key_technical_levels": {},
        "reasoning": reasoning,
    }
