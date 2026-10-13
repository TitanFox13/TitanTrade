"""Per-ticker trailing-stop state (HWM, trail price, TP1/pyramid flags).

Extracted from executor.py (behavior-preserving).
"""

from __future__ import annotations

import json
from typing import Any

from titantrade.config import STATE_DIR


# ---------------------------------------------------------------------------
# Trailing stop management
# ---------------------------------------------------------------------------

def _load_trailing_state() -> dict[str, Any]:
    path = STATE_DIR / "trailing_stops.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def _save_trailing_state(state: dict[str, Any]) -> None:
    with open(STATE_DIR / "trailing_stops.json", "w") as f:
        json.dump(state, f, indent=2)


def _cleanup_trailing_state(held_tickers: set[str]) -> None:
    """Remove trailing state for tickers that are no longer held."""
    state = _load_trailing_state()
    stale = [t for t in state if t not in held_tickers]
    for t in stale:
        del state[t]
    if stale:
        _save_trailing_state(state)
