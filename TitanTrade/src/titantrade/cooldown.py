"""Re-entry ABORT cooldown state + override policy.

Extracted from executor.py (behavior-preserving).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from titantrade.config import STATE_DIR
from titantrade.logger import get_logger

log = get_logger("cooldown")


# ---------------------------------------------------------------------------
# Re-entry cooldown (prevents whipsaw after ABORT)
# ---------------------------------------------------------------------------

# After we ABORT a ticker (sentry, price-check, or thesis-flip exit) we lock
# new entries on that ticker for this many hours. Without this, the executor
# would re-buy on the next run because Claude's weekly thesis is still
# BULLISH — producing the documented "sell low, buy higher" cycles (LLY and
# FCX each round-tripped 3+ times in a single week in prod logs).
REENTRY_COOLDOWN_HOURS = 72


def _load_abort_cooldowns() -> dict[str, dict[str, Any]]:
    """Return {ticker: {aborted_at, reason}} from disk."""
    path = STATE_DIR / "abort_cooldown.json"
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_abort_cooldowns(data: dict[str, dict[str, Any]]) -> None:
    with open(STATE_DIR / "abort_cooldown.json", "w") as f:
        json.dump(data, f, indent=2)


def _record_abort_cooldown(
    ticker: str, reason: str, exit_price: float | None = None,
) -> None:
    """Record an ABORT so re-entries are suppressed for REENTRY_COOLDOWN_HOURS.

    ``exit_price`` (the mark we sold at) anchors the override's recovery test
    (Decision 059); omitted/non-positive → the record carries none and the
    override falls back to the thesis-stop test.
    """
    data = _load_abort_cooldowns()
    record: dict[str, Any] = {
        "aborted_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason[:200],  # cap to keep file small
    }
    if exit_price and exit_price > 0:
        record["exit_price"] = float(exit_price)
    data[ticker] = record
    _save_abort_cooldowns(data)


def cooldown_exit_price(ticker: str) -> float | None:
    """The exit price stored with the ticker's active cooldown record, or None
    (no record, or a pre-Decision-059 record without one). Read-only."""
    entry = _load_abort_cooldowns().get(ticker) or {}
    try:
        price = float(entry.get("exit_price") or 0)
    except (TypeError, ValueError):
        return None
    return price if price > 0 else None


def _is_in_cooldown(ticker: str) -> tuple[bool, float]:
    """Return ``(in_cooldown, hours_since_abort)``.

    Also prunes expired entries (older than the cooldown window) so the file
    doesn't grow unbounded.
    """
    data = _load_abort_cooldowns()
    entry = data.get(ticker)
    if not entry:
        return False, 0.0
    try:
        aborted_at = datetime.fromisoformat(entry["aborted_at"])
    except (ValueError, KeyError, TypeError):
        # Bad data — clean up and don't apply
        data.pop(ticker, None)
        _save_abort_cooldowns(data)
        return False, 0.0
    hours = (datetime.now(timezone.utc) - aborted_at).total_seconds() / 3600
    if hours >= REENTRY_COOLDOWN_HOURS:
        # Expired — clean up
        data.pop(ticker, None)
        _save_abort_cooldowns(data)
        return False, hours
    return True, hours


def _record_stop_out_cooldown(
    ticker: str, exited_at: str, reason: str, exit_price: float | None = None,
) -> bool:
    """Record a broker-side stop-loss exit as a cooldown event (ADR 056).

    Unlike ``_record_abort_cooldown`` this stamps the cooldown clock with the
    stop order's FILL time, not now() — the scan that detects these runs on
    every executor cycle, and re-stamping with now() would silently extend the
    cooldown forever. Recording the fill time makes repeated detection of the
    same fill idempotent.

    Returns True when a new record was written, False when an equal-or-newer
    event already covers this ticker.
    """
    try:
        exited_dt = datetime.fromisoformat(exited_at)
    except (ValueError, TypeError):
        return False
    data = _load_abort_cooldowns()
    entry = data.get(ticker)
    if entry:
        try:
            existing_dt = datetime.fromisoformat(entry.get("aborted_at", ""))
            if existing_dt >= exited_dt:
                return False  # already covered by an equal-or-newer event
        except (ValueError, TypeError):
            pass  # damaged record — overwrite with the valid one
    record: dict[str, Any] = {
        # Normalize through fromisoformat→isoformat so _is_in_cooldown's
        # parser always accepts what we store (Alpaca stamps use 'Z').
        "aborted_at": exited_dt.isoformat(),
        "reason": reason[:200],
    }
    if exit_price and exit_price > 0:
        record["exit_price"] = float(exit_price)
    data[ticker] = record
    _save_abort_cooldowns(data)
    return True


# Minimum hours after ABORT before sentry-confirmed override can re-enter.
# A 24h buffer prevents same-day whipsaw round-trips (the GS case) while
# still allowing the recovery leg after a one-day shakeout.
COOLDOWN_OVERRIDE_MIN_HOURS = 24

# "Recovered" means the price is back at least this far ABOVE THE PRICE WE
# EXITED AT (Decision 059). Measured against the thesis stop alone, the test
# was satisfied by nearly every exit (a 3–5% abort or a stop-out both leave
# the price above the stop), so the 72h cooldown was effectively 24h and the
# system re-bought the same names at the same price a day later. Over the
# 23 override-population re-entries Jul 8 → Sep 28 2026, the 10 that came in
# less than 1% above the exit all lost (−$767 combined); the 13 that came in
# ≥1% above kept every winner (+$2,250).
COOLDOWN_RECOVERY_PCT = 1.0


def cooldown_override_allowed(
    ticker: str,
    thesis: dict[str, Any],
    sentry: dict[str, Any] | None,
    hours_since_abort: float,
    current_price: float | None,
    exit_price: float | None = None,
) -> bool:
    """Decide whether the daily sentry confirms it's safe to re-enter a
    ticker that's still in the 72h ABORT cooldown.

    Override only when ALL of these hold:
      - At least ``COOLDOWN_OVERRIDE_MIN_HOURS`` (24) have passed
      - The current weekly thesis is still BULLISH and selected for trading
      - The latest sentry signal is CONTINUE (not ABORT)
      - The current price has recovered above the thesis stop (price action
        confirms the thesis hasn't been invalidated)
      - When the cooldown record carries the exit price: the current price is
        at least ``COOLDOWN_RECOVERY_PCT`` above it (Decision 059) — a re-buy
        at the price we just sold at is the whipsaw the cooldown exists to
        stop, not a recovery. Records without an exit price (pre-059) keep
        the thesis-stop test only.

    Without this override, a single intraday whipsaw locks the ticker out
    for 72 hours — the GS case from production. With it, we re-enter on
    confirmed recovery; without all conditions we still respect the full
    cooldown.
    """
    if hours_since_abort < COOLDOWN_OVERRIDE_MIN_HOURS:
        return False
    if thesis.get("thesis") != "BULLISH" or not thesis.get("selected_for_trading"):
        return False
    if not sentry or sentry.get("signal") != "CONTINUE":
        return False
    stop = thesis.get("stop_loss_price")
    if not stop or not current_price:
        return False
    # Price must be at least 1% above the stop to qualify as "recovered"
    if current_price < stop * 1.01:
        return False
    # Decision 059: ...and at least COOLDOWN_RECOVERY_PCT above the exit.
    if exit_price and exit_price > 0:
        if current_price < exit_price * (1 + COOLDOWN_RECOVERY_PCT / 100):
            return False
    return True
