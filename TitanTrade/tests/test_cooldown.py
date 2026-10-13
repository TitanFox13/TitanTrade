"""Re-entry cooldown after a protective exit (Decisions 056/059)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from titantrade.cooldown import (
    COOLDOWN_RECOVERY_PCT, REENTRY_COOLDOWN_HOURS, _is_in_cooldown, _record_abort_cooldown,
    _record_stop_out_cooldown, cooldown_exit_price, cooldown_override_allowed,
)


class TestCooldownState:
    def test_record_check_and_expiry(self, tmp_state_dir):
        _record_abort_cooldown("AAA", "stop-out", exit_price=99.5)
        in_cd, hours = _is_in_cooldown("AAA")
        assert in_cd and hours < 0.1
        assert cooldown_exit_price("AAA") == pytest.approx(99.5)
        assert _is_in_cooldown("BBB") == (False, 0.0)
        old = (datetime.now(timezone.utc) - timedelta(hours=REENTRY_COOLDOWN_HOURS + 1)).isoformat()
        assert _record_stop_out_cooldown("CCC", old, "stop-loss exit", exit_price=50.0)
        assert _is_in_cooldown("CCC")[0] is False

    def test_stop_out_record_keeps_the_fill_time_and_is_idempotent(self, tmp_state_dir):
        filled = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        assert _record_stop_out_cooldown("DVN", filled, "stop-loss exit", exit_price=43.42)
        assert not _record_stop_out_cooldown("DVN", filled, "stop-loss exit", exit_price=43.42)
        saved = json.loads((tmp_state_dir / "abort_cooldown.json").read_text())["DVN"]
        assert saved["exit_price"] == pytest.approx(43.42) and saved["aborted_at"].startswith(filled[:16])


class TestOverride:
    def test_needs_24h_and_one_percent_above_the_exit(self):
        assert COOLDOWN_RECOVERY_PCT == 1.0
        assert cooldown_override_allowed(28, 343.50, 342.89) is False      # +0.2%: the flat re-buy
        assert cooldown_override_allowed(28, 342.89 * 1.01, 342.89) is True
        assert cooldown_override_allowed(20, 400.0, 342.89) is False       # too soon
        assert cooldown_override_allowed(28, 400.0, None) is False         # unknown exit → full cooldown
        assert cooldown_override_allowed(28, None, 342.89) is False
