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


def _record_abort_cooldown(ticker: str, reason: str) -> None:
    """Record an ABORT so re-entries are suppressed for REENTRY_COOLDOWN_HOURS."""
    data = _load_abort_cooldowns()
    data[ticker] = {
        "aborted_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason[:200],  # cap to keep file small
    }
    _save_abort_cooldowns(data)


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


# Minimum hours after ABORT before sentry-confirmed override can re-enter.
# A 24h buffer prevents same-day whipsaw round-trips (the GS case) while
# still allowing the recovery leg after a one-day shakeout.
COOLDOWN_OVERRIDE_MIN_HOURS = 24


def cooldown_override_allowed(
    ticker: str,
    thesis: dict[str, Any],
    sentry: dict[str, Any] | None,
    hours_since_abort: float,
    current_price: float | None,
) -> bool:
    """Decide whether the daily sentry confirms it's safe to re-enter a
    ticker that's still in the 72h ABORT cooldown.

    Override only when ALL of these hold:
      - At least ``COOLDOWN_OVERRIDE_MIN_HOURS`` (24) have passed
      - The current weekly thesis is still BULLISH and selected for trading
      - The latest sentry signal is CONTINUE (not ABORT)
      - The current price has recovered above the thesis stop (price action
        confirms the thesis hasn't been invalidated)

    Without this override, a single intraday whipsaw locks the ticker out
    for 72 hours — the GS case from production. With it, we re-enter on
    confirmed recovery; without all four conditions we still respect the
    full cooldown.
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
    return True
