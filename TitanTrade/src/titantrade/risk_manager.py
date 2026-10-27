"""Portfolio-level risk gates (Decisions 035/046/052/054/061/063).

Eight gates sit between the plan and the broker: earnings blackout, drawdown
circuit breaker, cash reserve, overlay cap, position size (flat slots),
sector exposure, macro blackout and correlation. All are evaluated on every
entry so a blocked entry reports every failing gate (near-miss detection).
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from titantrade.config import Config, STATE_DIR
from titantrade.logger import get_logger
from titantrade.market_context import get_stock_sector

log = get_logger("risk_manager")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_DRAWDOWN_PCT = 8.0          # Halt new entries if portfolio drops >8% from peak
MAX_SECTOR_EXPOSURE_PCT = 50.0  # Max % of equity in one sector
MIN_CASH_RESERVE_PCT = 5.0      # Cash is transit, not destination
MACRO_BLACKOUT_HOURS = 6        # No new entries within 6h of high-impact macro events

# Minimum dollar value for a new position. When nearly all cash is committed,
# the cash/overlay reductions in the sizing gate can shrink an order to
# fractional dust (production: URI 0.01 sh = $11, ANET 0.19 sh = $35 — all
# filled). Dust positions can't carry stops (Alpaca rejects stops on
# sub-1-share orders, ADR 052) and just generate churn and fees. Below this
# floor the trade isn't worth having: block instead.
MIN_POSITION_NOTIONAL = 500.0

# Single-observation deviation vs the recorded peak beyond which a broker-
# reported portfolio value is treated as corrupted data rather than market
# reality. A diversified long-only equity book cannot organically move ±50%
# between two executor runs; production saw Alpaca paper return $22,828
# against a real ~$100k equity mid-way through processing the CRWD 4:1 split
# (2026-07-07), tripping the drawdown breaker at a phantom "79.1%". The
# inverse glitch would silently corrupt peak_portfolio.json forever.
SUSPECT_VALUE_DEVIATION_PCT = 50.0

# Max % of equity across all overlay positions combined (3 × 25% slots trim
# the third to 20%), so the SPY core always keeps a floor.
MAX_TOTAL_OVERLAY_PCT = 0.70

# Only these specific macro events get the blackout. Production logs showed
# the previous 24h-on-everything rule blocking >50% of trading windows because
# FMP's economic calendar includes dozens of low-impact items (Atlanta Fed
# GDPNow, CB Employment Trends Index, retail ex-autos breakdowns, etc.). We
# now match by case-insensitive substring against the event name.
HIGH_IMPACT_MACRO_KEYWORDS: tuple[str, ...] = (
    "fomc",                 # Fed rate decision / minutes
    "nonfarm payrolls",     # Monthly NFP
    "cpi yoy",              # Consumer Price Index headline
    "cpi mom",              # Consumer Price Index monthly
    "core cpi",             # Core CPI variants
    "core pce price",       # Fed's preferred inflation gauge
    "ppi yoy",              # Producer Price Index headline
    "gdp growth rate",      # Quarterly GDP
    "unemployment rate",    # Headline unemployment
    "fed interest rate",    # Fed rate decisions
    "ecb interest rate",    # ECB (US equities react)
)

MAX_AVG_CORRELATION = 0.75      # Block entry if average correlation with held tickers > 75%


def _is_high_impact_macro(event_name: str) -> bool:
    """Match an event name (case-insensitive) against the high-impact list."""
    name = (event_name or "").lower()
    return any(kw in name for kw in HIGH_IMPACT_MACRO_KEYWORDS)


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
    """Update peak if current value is a new high. Returns the peak.

    Refuses implausible upward spikes (> SUSPECT_VALUE_DEVIATION_PCT above
    the recorded peak): a glitched broker value written into the peak file
    would permanently trip the drawdown breaker once real values return.
    """
    peak = load_peak_value()
    if peak > 0 and current_value > peak * (1 + SUSPECT_VALUE_DEVIATION_PCT / 100):
        log.warning(
            f"SUSPECT PORTFOLIO VALUE: ${current_value:,.2f} is >"
            f"{SUSPECT_VALUE_DEVIATION_PCT:.0f}% above peak ${peak:,.2f} — "
            f"likely broker data glitch, NOT recording as new peak"
        )
        _notify_suspect_value(current_value, peak)
        return peak
    if current_value > peak:
        peak = current_value
        with open(_peak_state_path(), "w") as f:
            json.dump({
                "peak_value": peak,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }, f, indent=2)
        log.info(f"New portfolio peak: ${peak:,.2f}")
    return peak


# Suspect-value Discord alerts are deduped: the gates run once per candidate
# ticker, so a single glitched executor run would otherwise fire 8+ webhooks.
_SUSPECT_ALERT_INTERVAL_S = 1800.0
_last_suspect_alert: float = 0.0


def _notify_suspect_value(observed: float, peak: float) -> None:
    global _last_suspect_alert
    now = time.monotonic()
    if _last_suspect_alert and now - _last_suspect_alert < _SUSPECT_ALERT_INTERVAL_S:
        return
    _last_suspect_alert = now
    try:
        from titantrade.notifier import notify_suspect_portfolio_value
        notify_suspect_portfolio_value(observed, peak)
    except Exception:  # noqa: BLE001 — alerting must never break the gates
        log.exception("Failed to send suspect-portfolio-value alert")


def check_drawdown_circuit_breaker(portfolio_value: float) -> tuple[bool, float]:
    """Check if portfolio drawdown exceeds the max allowed.

    Returns (is_tripped, drawdown_pct).
    If tripped, NO new entries should be made.

    A "drawdown" beyond SUSPECT_VALUE_DEVIATION_PCT is treated as broker data
    corruption (see the constant's comment): entries stay blocked — sitting
    out one run is cheap insurance either way — but the event is alerted as
    a data problem so the operator doesn't read it as a real 79% crash.
    """
    peak = load_peak_value()
    if peak > 0 and portfolio_value < peak * (1 - SUSPECT_VALUE_DEVIATION_PCT / 100):
        drawdown_pct = (peak - portfolio_value) / peak * 100
        log.warning(
            f"SUSPECT PORTFOLIO VALUE: ${portfolio_value:,.2f} is "
            f"{drawdown_pct:.1f}% below peak ${peak:,.2f} — likely broker "
            f"data glitch; blocking entries this run as a precaution"
        )
        _notify_suspect_value(portfolio_value, peak)
        return True, round(drawdown_pct, 2)

    peak = update_peak_value(portfolio_value)

    if peak <= 0:
        return False, 0.0

    drawdown_pct = max((peak - portfolio_value) / peak * 100, 0.0)

    if drawdown_pct >= MAX_DRAWDOWN_PCT:
        log.warning(
            f"CIRCUIT BREAKER TRIPPED: Portfolio ${portfolio_value:,.2f} is "
            f"{drawdown_pct:.1f}% below peak ${peak:,.2f} "
            f"(limit: {MAX_DRAWDOWN_PCT}%)"
        )
        return True, round(drawdown_pct, 2)

    return False, round(drawdown_pct, 2)


def max_investable_amount(
    portfolio_value: float,
    cash_balance: float,
    committed_cash: float = 0.0,
) -> float:
    """How much cash can we deploy while maintaining the minimum reserve?

    Returns the maximum dollar amount available for new positions.

    ``committed_cash`` is the notional of already-pending (unfilled) BUY
    orders. Entry brackets are day-limit orders that don't consume cash until
    they fill, so the raw ``cash_balance`` overstates what's truly free: N
    pending brackets can each pass this gate against the same settled cash,
    then all fill and drive the account into margin / negative cash (the
    production bug where cash hit -$6,379 with buying power at 2-3x portfolio).
    Subtracting committed cash makes the reserve hold across simultaneously
    pending entries.
    """
    min_cash = portfolio_value * (MIN_CASH_RESERVE_PCT / 100)
    available = max(cash_balance - min_cash - max(committed_cash, 0.0), 0)
    return available


def compute_overlay_headroom(
    positions: list[dict[str, Any]],
    portfolio_value: float,
    core_tickers: tuple[str, ...] = (),
) -> float:
    """Return dollar-value headroom in the AI-overlay sleeve.

    The "overlay sleeve" is everything in the portfolio that ISN'T the core
    position (SPY / hedge ETF). Capped at ``MAX_TOTAL_OVERLAY_PCT`` of total
    portfolio value. Returns 0 (no headroom) if we're already at or above
    the cap.

    The point: prevent four 0.95-confidence theses from each sizing at 25%
    and collectively consuming 100% of capital, starving the always-on SPY
    core allocation and any rebalancing buffer.
    """
    if portfolio_value <= 0:
        return 0.0
    overlay_value = sum(
        abs(float(p.get("market_value", 0)))
        for p in positions
        if p.get("symbol") not in core_tickers
    )
    cap_value = portfolio_value * MAX_TOTAL_OVERLAY_PCT
    return max(0.0, cap_value - overlay_value)


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
            # Only block on actually-market-moving events. Without this filter
            # we were locked out of trading >50% of the time because every
            # FMP-indexed economic indicator triggered the blackout.
            if not _is_high_impact_macro(event_name):
                continue
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


# ---------------------------------------------------------------------------
# Master pre-trade check: runs ALL gates
# ---------------------------------------------------------------------------

def pre_trade_check(
    ticker: str,
    item: dict[str, Any],
    portfolio_value: float,
    cash_balance: float,
    positions: list[dict[str, Any]],
    earnings_blocked: bool,
    cfg: Config,
    economic_calendar: list[dict[str, Any]] | None = None,
    correlation_matrix: dict[str, dict[str, float]] | None = None,
    committed_cash: float = 0.0,
) -> dict[str, Any]:
    """Run all eight gates for a plan item. Returns ``allowed``, ``reason``
    (first failure), ``shares``, ``flags``, ``failed_gates`` and per-gate
    ``gate_results`` — every gate is evaluated even after a failure so
    near-misses (<= 2 failing gates) can be surfaced."""
    result: dict[str, Any] = {
        "allowed": True, "reason": "", "shares": 0, "flags": [],
        "failed_gates": [], "gate_results": {},
    }
    entry_price = float(item.get("entry_price") or 0)

    def _fail(gate: str, detail: str) -> None:
        result["failed_gates"].append(gate)
        result["gate_results"][gate] = {"passed": False, "detail": detail}
        if not result["reason"]:
            result["reason"] = detail

    def _pass(gate: str, detail: str) -> None:
        result["gate_results"][gate] = {"passed": True, "detail": detail}

    # Gate 1: Earnings blackout
    if earnings_blocked:
        _fail("earnings", "Within earnings blackout window")
    else:
        _pass("earnings", "Not in earnings blackout")

    # Gate 2: Drawdown circuit breaker
    breaker_tripped, drawdown = check_drawdown_circuit_breaker(portfolio_value)
    if breaker_tripped:
        if drawdown >= SUSPECT_VALUE_DEVIATION_PCT:
            _fail("drawdown", f"Portfolio value ${portfolio_value:,.0f} deviates {drawdown:.0f}% from peak — suspect broker data, blocking as precaution")
        else:
            _fail("drawdown", f"Circuit breaker: {drawdown:.1f}% drawdown from peak")
    else:
        _pass("drawdown", f"Drawdown {drawdown:.1f}% within limit")
        if drawdown > MAX_DRAWDOWN_PCT * 0.7:
            result["flags"].append(f"WARNING: Drawdown at {drawdown:.1f}% (breaker at {MAX_DRAWDOWN_PCT}%)")

    # Gate 3: Cash reserve (net of cash committed to pending buys)
    investable = max_investable_amount(portfolio_value, cash_balance, committed_cash)
    if investable <= 0:
        detail = f"Insufficient cash after maintaining {MIN_CASH_RESERVE_PCT}% reserve"
        if committed_cash > 0:
            detail += f" (${committed_cash:,.0f} already committed to pending orders)"
        _fail("cash_reserve", detail)
    else:
        _pass("cash_reserve", f"${investable:,.2f} available after reserve")

    # Gate 4: Overlay cap (core excluded)
    overlay_headroom = compute_overlay_headroom(
        positions, portfolio_value, core_tickers=(cfg.trading.core_ticker, cfg.trading.momentum_ticker),
    )

    # Gate 5: Position size — a flat slot, reduced by cash and overlay headroom
    shares = 0.0
    if investable > 0 and entry_price > 0:
        raw = portfolio_value * cfg.trading.overlay_slot_pct / entry_price
        shares = float(int(raw)) if raw >= 1.0 else round(raw, 2)
        position_value = shares * entry_price
        if position_value > investable:
            raw = investable / entry_price
            shares = float(int(raw)) if raw >= 1.0 else round(raw, 2)
            position_value = shares * entry_price
            result["flags"].append(f"Position reduced to {shares} shares (cash reserve)")
        if position_value > overlay_headroom:
            if overlay_headroom <= 0:
                _fail("overlay_cap", f"Overlay sleeve at cap ({MAX_TOTAL_OVERLAY_PCT:.0%}); existing positions already saturate the budget")
                shares = 0.0
            else:
                raw = overlay_headroom / entry_price
                shares = float(int(raw)) if raw >= 1.0 else round(raw, 2)
                position_value = shares * entry_price
                result["flags"].append(f"Position reduced to {shares} shares (overlay cap, ${overlay_headroom:,.0f} headroom)")
        if 0 < shares * entry_price < MIN_POSITION_NOTIONAL:
            _fail("position_size", f"Position ${shares * entry_price:,.0f} below ${MIN_POSITION_NOTIONAL:,.0f} minimum notional (dust)")
            shares = 0.0
        elif shares <= 0 and "overlay_cap" not in result["failed_gates"]:
            _fail("position_size", f"Position size is 0 shares at ${entry_price}")
        elif shares > 0:
            pct = shares * entry_price / portfolio_value * 100 if portfolio_value > 0 else 0
            _pass("position_size", f"{shares} shares ({pct:.1f}% of portfolio)")
            if "overlay_cap" not in result["failed_gates"]:
                _pass("overlay_cap", f"${overlay_headroom:,.0f} headroom in overlay sleeve (cap {MAX_TOTAL_OVERLAY_PCT:.0%})")
    elif investable <= 0:
        result["gate_results"]["position_size"] = {"passed": False, "detail": "Not evaluated (cash reserve failed)"}
    else:
        _fail("position_size", f"Position size is 0 shares at ${entry_price}")

    # Gate 6: Sector exposure
    if shares > 0:
        sector_allowed, sector_pct = check_sector_limit(ticker, shares * entry_price, [p for p in positions if p.get('symbol') not in (cfg.trading.core_ticker, cfg.trading.momentum_ticker)], portfolio_value)   # core legs are not sector exposure
        if not sector_allowed:
            _fail("sector_exposure", f"Sector exposure would exceed {MAX_SECTOR_EXPOSURE_PCT}%")
        else:
            _pass("sector_exposure", f"Sector at {sector_pct:.1f}%")
            if sector_pct > MAX_SECTOR_EXPOSURE_PCT * 0.7:
                result["flags"].append(f"WARNING: {get_stock_sector(ticker)} sector at {sector_pct:.1f}%")
    else:
        result["gate_results"].setdefault("sector_exposure", {"passed": False, "detail": "Not evaluated (no shares to size)"})

    # Gate 7: Macro blackout
    if economic_calendar:
        macro_blocked, macro_event = check_macro_blackout(economic_calendar)
        if macro_blocked:
            _fail("macro_blackout", f"Macro event within {MACRO_BLACKOUT_HOURS}h: {macro_event}")
        else:
            _pass("macro_blackout", "No major macro events imminent")
    else:
        _pass("macro_blackout", "No economic calendar data (skipped)")

    # Gate 8: Correlation with the held names
    if correlation_matrix and shares > 0:
        held = [p.get("symbol", "") for p in positions]
        corr_allowed, avg_corr = check_correlation_limit(ticker, held, correlation_matrix)
        if not corr_allowed:
            _fail("correlation", f"Avg correlation {avg_corr:.2f} with held positions exceeds {MAX_AVG_CORRELATION}")
        else:
            _pass("correlation", f"Avg correlation {avg_corr:.2f} within limit")
    else:
        _pass("correlation", "No correlation data (skipped)")

    if result["failed_gates"]:
        result["allowed"] = False
        result["shares"] = 0
    else:
        result["shares"] = shares
    return result
