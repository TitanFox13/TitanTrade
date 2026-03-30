"""Portfolio-level risk management: circuit breakers, vol-adjusted sizing, sector limits.

Individual stop-losses protect per-position. This module protects the whole portfolio
from correlated selloffs, overconcentration, and volatility mismatches.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from titantrade.config import Config, STATE_DIR
from titantrade.indicators import atr
from titantrade.logger import get_logger
from titantrade.market_context import get_stock_sector

log = get_logger("risk_manager")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_DRAWDOWN_PCT = 8.0          # Halt new entries if portfolio drops >8% from peak
MAX_SECTOR_EXPOSURE_PCT = 40.0  # No more than 40% of portfolio in one sector
MIN_CASH_RESERVE_PCT = 20.0     # Always keep 20% cash for opportunities
MIN_CONFIDENCE = 0.70           # Only trade when AI confidence >= 70%
ATR_RISK_BUDGET = 0.02          # Target 2% of portfolio at risk per position (ATR-based)
MACRO_BLACKOUT_HOURS = 24       # No new entries within 24h of major macro events
MAX_AVG_CORRELATION = 0.75      # Block entry if average correlation with held tickers > 75%


# ---------------------------------------------------------------------------
# Peak portfolio tracking (for drawdown circuit breaker)
# ---------------------------------------------------------------------------

def _peak_state_path():
    return STATE_DIR / "peak_portfolio.json"


def load_peak_value() -> float:
    """Load the recorded portfolio peak from state."""
    path = _peak_state_path()
    if not path.exists():
        return 0.0
    with open(path) as f:
        data = json.load(f)
    return data.get("peak_value", 0.0)


def update_peak_value(current_value: float) -> float:
    """Update peak if current value is a new high. Returns the peak."""
    peak = load_peak_value()
    if current_value > peak:
        peak = current_value
        with open(_peak_state_path(), "w") as f:
            json.dump({
                "peak_value": peak,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }, f, indent=2)
        log.info(f"New portfolio peak: ${peak:,.2f}")
    return peak


def check_drawdown_circuit_breaker(portfolio_value: float) -> tuple[bool, float]:
    """Check if portfolio drawdown exceeds the max allowed.

    Returns (is_tripped, drawdown_pct).
    If tripped, NO new entries should be made.
    """
    peak = update_peak_value(portfolio_value)

    if peak <= 0:
        return False, 0.0

    drawdown_pct = (peak - portfolio_value) / peak * 100

    if drawdown_pct >= MAX_DRAWDOWN_PCT:
        log.warning(
            f"CIRCUIT BREAKER TRIPPED: Portfolio ${portfolio_value:,.2f} is "
            f"{drawdown_pct:.1f}% below peak ${peak:,.2f} "
            f"(limit: {MAX_DRAWDOWN_PCT}%)"
        )
        return True, round(drawdown_pct, 2)

    return False, round(drawdown_pct, 2)


# ---------------------------------------------------------------------------
# Cash reserve enforcement
# ---------------------------------------------------------------------------

def max_investable_amount(portfolio_value: float, cash_balance: float) -> float:
    """How much cash can we deploy while maintaining the minimum reserve?

    Returns the maximum dollar amount available for new positions.
    """
    min_cash = portfolio_value * (MIN_CASH_RESERVE_PCT / 100)
    available = max(cash_balance - min_cash, 0)
    return available


# ---------------------------------------------------------------------------
# Sector exposure check
# ---------------------------------------------------------------------------

def calculate_sector_exposure(
    positions: list[dict[str, Any]], portfolio_value: float
) -> dict[str, float]:
    """Calculate what % of portfolio is in each sector.

    Returns dict of sector -> exposure percentage.
    """
    sector_values: dict[str, float] = {}

    for pos in positions:
        ticker = pos.get("symbol", "")
        market_value = abs(float(pos.get("market_value", 0)))
        sector = get_stock_sector(ticker)
        sector_values[sector] = sector_values.get(sector, 0) + market_value

    if portfolio_value <= 0:
        return {}

    return {
        sector: round(value / portfolio_value * 100, 2)
        for sector, value in sector_values.items()
    }


def check_sector_limit(
    ticker: str,
    position_value: float,
    positions: list[dict[str, Any]],
    portfolio_value: float,
) -> tuple[bool, float]:
    """Check if adding this position would breach sector exposure limits.

    Returns (is_allowed, current_sector_exposure_pct).
    """
    sector = get_stock_sector(ticker)
    exposures = calculate_sector_exposure(positions, portfolio_value)
    current = exposures.get(sector, 0.0)

    new_exposure = current + (position_value / portfolio_value * 100) if portfolio_value > 0 else 0

    if new_exposure > MAX_SECTOR_EXPOSURE_PCT:
        log.warning(
            f"SECTOR LIMIT: {ticker} ({sector}) would push exposure to "
            f"{new_exposure:.1f}% (limit: {MAX_SECTOR_EXPOSURE_PCT}%)"
        )
        return False, current

    return True, current


# ---------------------------------------------------------------------------
# Volatility-adjusted position sizing
# ---------------------------------------------------------------------------

def volatility_adjusted_shares(
    portfolio_value: float,
    entry_price: float,
    stock_atr: float | None,
    risk_per_trade_pct: float = 0.10,
) -> float:
    """Calculate shares using ATR-based risk budgeting.

    Standard approach: fixed dollar risk per trade, scaled by volatility.
    Returns fractional shares (rounded to 2 decimals) to support small accounts.

    If ATR is available:
      dollar_risk = portfolio_value * ATR_RISK_BUDGET
      shares = dollar_risk / ATR
      But cap at risk_per_trade_pct * portfolio_value (the old fixed limit)

    If ATR is unavailable, fall back to fixed percentage sizing.
    """
    max_position_value = portfolio_value * risk_per_trade_pct

    def _snap(raw: float) -> float:
        """Use whole shares when possible, fractional only for small positions."""
        if raw >= 1.0:
            return float(int(raw))
        return round(raw, 2)

    if stock_atr is None or stock_atr <= 0:
        # Fallback: fixed percentage
        shares = _snap(max_position_value / entry_price) if entry_price > 0 else 0.0
        return max(shares, 0.0)

    # ATR-based: risk ATR_RISK_BUDGET of portfolio per 1-ATR move
    dollar_risk_budget = portfolio_value * ATR_RISK_BUDGET
    atr_shares = _snap(dollar_risk_budget / stock_atr)

    # Cap by the maximum position value (don't exceed 10% regardless)
    max_shares = _snap(max_position_value / entry_price) if entry_price > 0 else 0.0

    shares = min(atr_shares, max_shares)
    position_pct = (shares * entry_price / portfolio_value * 100) if portfolio_value > 0 else 0

    log.info(
        f"Vol-adjusted sizing: ATR=${stock_atr:.2f}, "
        f"shares={shares} ({position_pct:.1f}% of portfolio)"
    )

    return max(shares, 0.0)


# ---------------------------------------------------------------------------
# Confidence threshold
# ---------------------------------------------------------------------------

def check_macro_blackout(economic_calendar: list[dict[str, Any]]) -> tuple[bool, str]:
    """Check if a major macro event is within MACRO_BLACKOUT_HOURS.

    Returns (is_blocked, event_description).
    """
    if not economic_calendar:
        return False, ""

    now = datetime.now(timezone.utc)
    for event in economic_calendar:
        event_date_str = event.get("date", "")
        if not event_date_str:
            continue
        try:
            event_dt = datetime.fromisoformat(event_date_str.replace("Z", "+00:00"))
            if event_dt.tzinfo is None:
                event_dt = event_dt.replace(hour=14, tzinfo=timezone.utc)
        except (ValueError, TypeError):
            try:
                event_dt = datetime(
                    *[int(x) for x in event_date_str[:10].split("-")],
                    hour=14, tzinfo=timezone.utc,
                )
            except (ValueError, TypeError):
                continue

        hours_until = (event_dt - now).total_seconds() / 3600
        if 0 <= hours_until <= MACRO_BLACKOUT_HOURS:
            event_name = event.get("event", "Unknown macro event")
            log.warning(
                f"MACRO BLACKOUT: {event_name} in {hours_until:.0f}h — "
                f"blocking new entries"
            )
            return True, event_name

    return False, ""


def check_correlation_limit(
    ticker: str,
    held_tickers: list[str],
    correlation_matrix: dict[str, dict[str, float]],
) -> tuple[bool, float]:
    """Check if adding this ticker would make the portfolio too correlated.

    Returns (is_allowed, avg_correlation_with_held).
    """
    if not held_tickers or ticker not in correlation_matrix:
        return True, 0.0

    corrs = []
    ticker_corrs = correlation_matrix.get(ticker, {})
    for held in held_tickers:
        c = ticker_corrs.get(held)
        if c is not None:
            corrs.append(c)

    if not corrs:
        return True, 0.0

    avg_corr = sum(corrs) / len(corrs)

    if avg_corr > MAX_AVG_CORRELATION:
        log.warning(
            f"CORRELATION LIMIT: {ticker} avg correlation {avg_corr:.2f} "
            f"with held positions exceeds {MAX_AVG_CORRELATION}"
        )
        return False, round(avg_corr, 3)

    return True, round(avg_corr, 3)


def passes_confidence_threshold(
    ticker: str, confidence: float, threshold: float = MIN_CONFIDENCE
) -> bool:
    """Check if AI confidence meets minimum threshold."""
    if confidence < threshold:
        log.info(
            f"LOW CONFIDENCE: {ticker} confidence {confidence:.2f} "
            f"below threshold {threshold:.2f} - skipping"
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Master pre-trade check: runs ALL risk gates
# ---------------------------------------------------------------------------

def pre_trade_check(
    ticker: str,
    thesis: dict[str, Any],
    portfolio_value: float,
    cash_balance: float,
    positions: list[dict[str, Any]],
    stock_atr: float | None,
    earnings_blocked: bool,
    cfg: Config,
    economic_calendar: list[dict[str, Any]] | None = None,
    correlation_matrix: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    """Run all risk checks before allowing a trade.

    Evaluates ALL 6 gates regardless of failures so we can report which gates
    blocked and detect near-misses (blocked by only 1-2 gates).

    Returns a dict with:
      allowed: bool
      reason: str (first failure reason, for backwards compat)
      shares: int (if allowed)
      flags: list of warning strings
      failed_gates: list of gate names that failed
      gate_results: dict of gate_name -> {"passed": bool, "detail": str}
    """
    result: dict[str, Any] = {
        "allowed": True,
        "reason": "",
        "shares": 0,
        "flags": [],
        "failed_gates": [],
        "gate_results": {},
    }

    entry_price = thesis.get("target_entry_price", 0)
    confidence = thesis.get("confidence", 0)

    def _fail(gate: str, detail: str) -> None:
        result["failed_gates"].append(gate)
        result["gate_results"][gate] = {"passed": False, "detail": detail}
        if not result["reason"]:
            result["reason"] = detail

    def _pass(gate: str, detail: str) -> None:
        result["gate_results"][gate] = {"passed": True, "detail": detail}

    # Gate 1: Confidence threshold
    if not passes_confidence_threshold(ticker, confidence):
        _fail("confidence", f"Confidence {confidence:.2f} below threshold {MIN_CONFIDENCE}")
    else:
        _pass("confidence", f"Confidence {confidence:.2f} >= {MIN_CONFIDENCE}")

    # Gate 2: Earnings blackout
    if earnings_blocked:
        _fail("earnings", "Within earnings blackout window")
    else:
        _pass("earnings", "Not in earnings blackout")

    # Gate 3: Drawdown circuit breaker
    breaker_tripped, drawdown = check_drawdown_circuit_breaker(portfolio_value)
    if breaker_tripped:
        _fail("drawdown", f"Circuit breaker: {drawdown:.1f}% drawdown from peak")
    else:
        _pass("drawdown", f"Drawdown {drawdown:.1f}% within limit")
        if drawdown > MAX_DRAWDOWN_PCT * 0.7:
            result["flags"].append(f"WARNING: Drawdown at {drawdown:.1f}% (breaker at {MAX_DRAWDOWN_PCT}%)")

    # Gate 4: Cash reserve
    investable = max_investable_amount(portfolio_value, cash_balance)
    if investable <= 0:
        _fail("cash_reserve", f"Insufficient cash after maintaining {MIN_CASH_RESERVE_PCT}% reserve")
    else:
        _pass("cash_reserve", f"${investable:,.2f} available after reserve")

    # Gate 5: Position sizing (depends on gate 4 passing)
    shares = 0.0
    if investable > 0 and entry_price > 0:
        shares = volatility_adjusted_shares(
            portfolio_value, entry_price, stock_atr, cfg.trading.risk_per_trade
        )
        position_value = shares * entry_price

        # Reduce if exceeding investable cash
        if position_value > investable:
            raw = investable / entry_price
            shares = float(int(raw)) if raw >= 1.0 else round(raw, 2)
            position_value = shares * entry_price
            result["flags"].append(f"Position reduced to {shares} shares (cash reserve)")

        if shares <= 0:
            _fail("position_size", f"Position size is 0 shares at ${entry_price}")
        else:
            pct = (shares * entry_price / portfolio_value * 100) if portfolio_value > 0 else 0
            _pass("position_size", f"{shares} shares ({pct:.1f}% of portfolio)")
    elif investable <= 0:
        result["gate_results"]["position_size"] = {
            "passed": False, "detail": "Not evaluated (cash reserve failed)",
        }
    else:
        _fail("position_size", f"Position size is 0 shares at ${entry_price}")

    # Gate 6: Sector exposure (uses computed shares from gate 5)
    if shares > 0:
        position_value = shares * entry_price
        sector_allowed, sector_pct = check_sector_limit(
            ticker, position_value, positions, portfolio_value
        )
        if not sector_allowed:
            _fail("sector_exposure", f"Sector exposure would exceed {MAX_SECTOR_EXPOSURE_PCT}%")
        else:
            _pass("sector_exposure", f"Sector at {sector_pct:.1f}%")
            if sector_pct > MAX_SECTOR_EXPOSURE_PCT * 0.7:
                sector = get_stock_sector(ticker)
                result["flags"].append(f"WARNING: {sector} sector at {sector_pct:.1f}%")
    else:
        result["gate_results"].setdefault("sector_exposure", {
            "passed": False, "detail": "Not evaluated (no shares to size)",
        })

    # Gate 7: Macro blackout
    if economic_calendar:
        macro_blocked, macro_event = check_macro_blackout(economic_calendar)
        if macro_blocked:
            _fail("macro_blackout", f"Macro event within {MACRO_BLACKOUT_HOURS}h: {macro_event}")
        else:
            _pass("macro_blackout", "No major macro events imminent")
    else:
        _pass("macro_blackout", "No economic calendar data (skipped)")

    # Gate 8: Correlation limit
    if correlation_matrix and shares > 0:
        held = [p.get("symbol", "") for p in positions]
        corr_allowed, avg_corr = check_correlation_limit(ticker, held, correlation_matrix)
        if not corr_allowed:
            _fail("correlation", f"Avg correlation {avg_corr:.2f} with held positions exceeds {MAX_AVG_CORRELATION}")
        else:
            _pass("correlation", f"Avg correlation {avg_corr:.2f} within limit")
    else:
        _pass("correlation", "No correlation data (skipped)")

    # Final determination
    if result["failed_gates"]:
        result["allowed"] = False
        result["shares"] = 0
    else:
        result["shares"] = shares

    return result
