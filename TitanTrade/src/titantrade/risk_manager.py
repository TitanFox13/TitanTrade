"""Portfolio-level risk management: circuit breakers, vol-adjusted sizing, sector limits.

Individual stop-losses protect per-position. This module protects the whole portfolio
from correlated selloffs, overconcentration, and volatility mismatches.
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

# --- Strategic recalibration: "Always Deployed, Asymmetric Exposure" ---
#
# Prior values caused 83%+ cash-drag in production despite a rising market:
#   MIN_CONFIDENCE=0.70 rejected ~all 0.65-0.69 ideas (the modal range).
#   MIN_CASH_RESERVE_PCT=20.0 reserved capital that was never deployed
#   anyway because of the confidence + sector + macro gates downstream.
#
# New posture: floors are looser, sizing is the lever. Sizing scales steeply
# with confidence so we ride high-conviction ideas hard, take small probes
# on low-conviction ones, and skip only when the thesis is actively bearish.
MAX_DRAWDOWN_PCT = 8.0          # Halt new entries if portfolio drops >8% from peak
MAX_SECTOR_EXPOSURE_PCT = 50.0  # Allow tighter sector concentration when conviction warrants
MIN_CASH_RESERVE_PCT = 5.0      # Cash is transit, not destination
MIN_CONFIDENCE = 0.55           # Floor: take small probes at 0.55, scale up sharply with conviction
ATR_RISK_BUDGET = 0.025         # 2.5% of portfolio risk per 1-ATR adverse move
MACRO_BLACKOUT_HOURS = 6        # No new entries within 6h of high-impact macro events

# Max % of portfolio in a single position (the ceiling that confidence-sizing
# cannot exceed). Up from the de-facto ~10% cap so a 0.95-confidence thesis
# can take a real position, not a token one.
MAX_POSITION_PCT = 0.25

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

# Max % of portfolio across all AI-overlay positions combined. Caps the
# total stock-picking sleeve so the always-deployed core (30% SPY by default)
# always has room. Without this cap, four 0.85-confidence theses at 17.5%
# each would consume 70% — fine — but four 0.95-confidence at 25% each would
# blow through the SPY allocation and starve the core rebalancer. The cap is
# also a defense against AI confidence inflation in benign markets.
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


def _is_high_impact_macro(event_name: str) -> bool:
    """Match an event name (case-insensitive) against the high-impact list."""
    name = (event_name or "").lower()
    return any(kw in name for kw in HIGH_IMPACT_MACRO_KEYWORDS)
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


# ---------------------------------------------------------------------------
# Cash reserve enforcement
# ---------------------------------------------------------------------------

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
# Confidence-scaled risk
# ---------------------------------------------------------------------------

def vix_scaled_risk(base_risk_pct: float, vix: float | None) -> float:
    """Scale risk_per_trade by the volatility environment.

    The principle: position sizes should reflect how dangerous the regime is.
    Calm markets reward courage; high-vol markets punish it. ATR-based sizing
    handles the *per-stock* volatility, but a portfolio-level VIX scaler
    handles the *market* one.

    Anchor points:
      VIX  < 15  → 1.2x (calm, low risk premium, lean in)
      VIX 15-25  → 1.0x (normal)
      VIX 25-35  → 0.7x (elevated, trim positions)
      VIX  > 35  → 0.4x (high stress, defensive sizing)

    If VIX is unavailable (None), returns base risk unchanged — we don't
    penalize sizing for missing data, the per-stock ATR still protects.
    """
    if vix is None or vix <= 0:
        return base_risk_pct

    if vix < 15:
        mult = 1.2
    elif vix < 25:
        # Linear interp between 15 (1.2) and 25 (1.0). At 20: 1.1.
        mult = 1.2 - (vix - 15) / 10 * 0.2
    elif vix < 35:
        # Linear interp between 25 (1.0) and 35 (0.7).
        mult = 1.0 - (vix - 25) / 10 * 0.3
    elif vix < 50:
        # Linear interp between 35 (0.7) and 50 (0.4).
        mult = 0.7 - (vix - 35) / 15 * 0.3
    else:
        mult = 0.4

    return round(base_risk_pct * mult, 4)


def confidence_scaled_risk(
    base_risk_pct: float,
    confidence: float,
    min_confidence: float = MIN_CONFIDENCE,
) -> float:
    """Scale risk_per_trade by confidence with a steep, piecewise curve.

    The old curve (0.7x at the floor, 1.3x at conf=1.0) was too flat: a
    0.95-confidence "high-conviction" idea was sized just 1.3x a 0.70 "barely
    passes the gate" idea. We want conviction to actually translate into
    size — small probes at the floor, real positions in the sweet spot,
    aggressive when the model is screaming.

    Anchor points (returned as multipliers of base_risk_pct):
      conf 0.55 → 0.40x   (tiny probe)
      conf 0.65 → 0.80x
      conf 0.70 → 1.00x   (the old baseline — preserved for backwards compat)
      conf 0.80 → 1.50x
      conf 0.90 → 2.00x
      conf 0.95+ → 2.50x  (cap)

    Below ``min_confidence`` the multiplier clamps to the floor's value
    rather than going negative.
    """
    # Piecewise-linear interpolation between anchor points.
    anchors = [
        (0.55, 0.40),
        (0.65, 0.80),
        (0.70, 1.00),
        (0.80, 1.50),
        (0.90, 2.00),
        (0.95, 2.50),
        (1.00, 2.50),
    ]
    c = max(min(confidence, 1.0), min_confidence)

    multiplier = anchors[0][1]
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
        if x0 <= c <= x1:
            if x1 == x0:
                multiplier = y1
            else:
                multiplier = y0 + (c - x0) * (y1 - y0) / (x1 - x0)
            break
    else:
        multiplier = anchors[-1][1]

    return round(base_risk_pct * multiplier, 4)


# ---------------------------------------------------------------------------
# Volatility-adjusted position sizing
# ---------------------------------------------------------------------------

def volatility_adjusted_shares(
    portfolio_value: float,
    entry_price: float,
    stock_atr: float | None,
    risk_per_trade_pct: float = 0.10,
    confidence: float | None = None,
    vix: float | None = None,
) -> float:
    """Calculate shares using ATR-based risk budgeting.

    Standard approach: fixed dollar risk per trade, scaled by volatility.
    Returns fractional shares (rounded to 2 decimals) to support small accounts.

    If ATR is available:
      dollar_risk = portfolio_value * ATR_RISK_BUDGET
      shares = dollar_risk / ATR
      But cap at risk_per_trade_pct * portfolio_value (the old fixed limit)

    If ATR is unavailable, fall back to fixed percentage sizing.

    If confidence is provided, scales risk_per_trade proportionally:
    low confidence (0.70) → smaller position, high confidence (1.0) → larger position.
    """
    if confidence is not None:
        risk_per_trade_pct = confidence_scaled_risk(risk_per_trade_pct, confidence)
    if vix is not None:
        # VIX scaling applies AFTER confidence scaling — so a 0.95-conf trade
        # in a VIX=35 market is still sized down (2.5x × 0.7x = 1.75x base).
        risk_per_trade_pct = vix_scaled_risk(risk_per_trade_pct, vix)
    # Confidence×VIX-scaled risk can exceed the base — cap so a single
    # high-conviction position can't take the whole portfolio.
    # MAX_POSITION_PCT is the hard ceiling no amount of conviction overrides.
    risk_per_trade_pct = min(risk_per_trade_pct, MAX_POSITION_PCT)
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
    vix: float | None = None,
    committed_cash: float = 0.0,
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
    # Use Pass-2's adjusted_confidence when present — that's Claude's
    # portfolio-aware refinement of the per-stock Pass-1 confidence. Falls
    # back to the original Pass-1 confidence for theses that didn't go
    # through Pass 2 (e.g. existing held positions on their first review).
    confidence = thesis.get("adjusted_confidence")
    if confidence is None:
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
        if drawdown >= SUSPECT_VALUE_DEVIATION_PCT:
            _fail(
                "drawdown",
                f"Portfolio value ${portfolio_value:,.0f} deviates "
                f"{drawdown:.0f}% from peak — suspect broker data, "
                f"blocking as precaution",
            )
        else:
            _fail("drawdown", f"Circuit breaker: {drawdown:.1f}% drawdown from peak")
    else:
        _pass("drawdown", f"Drawdown {drawdown:.1f}% within limit")
        if drawdown > MAX_DRAWDOWN_PCT * 0.7:
            result["flags"].append(f"WARNING: Drawdown at {drawdown:.1f}% (breaker at {MAX_DRAWDOWN_PCT}%)")

    # Gate 4: Cash reserve (net of cash already committed to pending buy orders)
    investable = max_investable_amount(portfolio_value, cash_balance, committed_cash)
    if investable <= 0:
        detail = f"Insufficient cash after maintaining {MIN_CASH_RESERVE_PCT}% reserve"
        if committed_cash > 0:
            detail += f" (${committed_cash:,.0f} already committed to pending orders)"
        _fail("cash_reserve", detail)
    else:
        _pass("cash_reserve", f"${investable:,.2f} available after reserve")

    # Gate 4b: Overlay-sleeve cap
    # Prevents the AI-pick sleeve from consuming so much portfolio value that
    # the always-on SPY core has no room. Core tickers are excluded from the
    # cap (they belong to a separate allocation budget).
    core_tickers: tuple[str, ...] = (
        cfg.trading.core_ticker,
        cfg.trading.core_hedge_ticker,
    )
    overlay_headroom = compute_overlay_headroom(
        positions, portfolio_value, core_tickers=core_tickers,
    )

    # Gate 5: Position sizing (depends on gate 4 passing)
    shares = 0.0
    if investable > 0 and entry_price > 0:
        shares = volatility_adjusted_shares(
            portfolio_value, entry_price, stock_atr, cfg.trading.risk_per_trade,
            confidence=confidence, vix=vix,
        )
        position_value = shares * entry_price

        # Reduce if exceeding investable cash
        if position_value > investable:
            raw = investable / entry_price
            shares = float(int(raw)) if raw >= 1.0 else round(raw, 2)
            position_value = shares * entry_price
            result["flags"].append(f"Position reduced to {shares} shares (cash reserve)")

        # Reduce if exceeding overlay-sleeve headroom (keeps room for core)
        if position_value > overlay_headroom:
            if overlay_headroom <= 0:
                _fail(
                    "overlay_cap",
                    f"Overlay sleeve at cap ({MAX_TOTAL_OVERLAY_PCT:.0%}); "
                    f"existing AI positions already saturate the budget",
                )
                shares = 0.0
            else:
                raw = overlay_headroom / entry_price
                shares = float(int(raw)) if raw >= 1.0 else round(raw, 2)
                position_value = shares * entry_price
                result["flags"].append(
                    f"Position reduced to {shares} shares "
                    f"(overlay cap, ${overlay_headroom:,.0f} headroom)"
                )

        # Dust guard: an order that survives the cash/overlay reductions can
        # still be economically meaningless. Block below the notional floor.
        if 0 < shares * entry_price < MIN_POSITION_NOTIONAL:
            _fail(
                "position_size",
                f"Position ${shares * entry_price:,.0f} below "
                f"${MIN_POSITION_NOTIONAL:,.0f} minimum notional (dust)",
            )
            shares = 0.0
        elif shares <= 0 and "overlay_cap" not in result["failed_gates"]:
            _fail("position_size", f"Position size is 0 shares at ${entry_price}")
        elif shares > 0:
            pct = (shares * entry_price / portfolio_value * 100) if portfolio_value > 0 else 0
            _pass("position_size", f"{shares} shares ({pct:.1f}% of portfolio)")
            if "overlay_cap" not in result.get("failed_gates", []):
                _pass(
                    "overlay_cap",
                    f"${overlay_headroom:,.0f} headroom in overlay sleeve "
                    f"(cap {MAX_TOTAL_OVERLAY_PCT:.0%})",
                )
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
