"""Tests for dynamic entry price adjustment on bracket resubmission.

Pure logic — no API calls, no mocks needed.
"""

from __future__ import annotations

import pytest

from titantrade.executor import _adjust_entry_price


@pytest.fixture
def thesis():
    return {
        "target_entry_price": 185.50,
        "stop_loss_price": 176.23,
        "take_profit_price": 198.00,
        "key_technical_levels": {
            "support": 183.00,
            "resistance": 195.00,
        },
    }


class TestAdjustmentLogic:
    def test_at_or_below_original_entry_uses_original(self, thesis):
        result = _adjust_entry_price(thesis, current_price=184.00)
        entry, stop, tp = result
        assert entry == 185.50
        assert stop == 176.23
        assert tp == 198.00

    def test_above_entry_adjusts_upward(self, thesis):
        result = _adjust_entry_price(thesis, current_price=190.00)
        entry, stop, tp = result
        # Should be ~0.5% below current
        assert entry > 185.50
        assert entry < 190.00

    def test_preserves_risk_ratio(self, thesis):
        original_risk = (185.50 - 176.23) / 185.50
        result = _adjust_entry_price(thesis, current_price=190.00)
        entry, stop, tp = result
        new_risk = (entry - stop) / entry
        # Risk ratio should be approximately the same
        assert abs(new_risk - original_risk) < 0.005

    def test_uses_support_when_close(self, thesis):
        """If price is within 1% of support, use support as entry."""
        result = _adjust_entry_price(thesis, current_price=183.50)
        # Price at 183.50 is within 1% of support at 183.00
        # But also below original entry, so should return original
        entry, stop, tp = result
        assert entry == 185.50  # Below original, so original returned


class TestChaseLimit:
    def test_returns_none_when_price_too_high(self, thesis):
        """Don't chase: skip if price is >5% above original entry."""
        result = _adjust_entry_price(thesis, current_price=200.00)
        assert result is None

    def test_returns_none_when_price_below_stop(self, thesis):
        """Thesis invalidated: skip if price is below original stop."""
        result = _adjust_entry_price(thesis, current_price=170.00)
        assert result is None


class TestStopFloors:
    def test_stop_never_below_original(self, thesis):
        result = _adjust_entry_price(thesis, current_price=188.00)
        entry, stop, tp = result
        assert stop >= 176.23

    def test_take_profit_adjusts_with_resistance(self, thesis):
        result = _adjust_entry_price(thesis, current_price=190.00)
        entry, stop, tp = result
        # Should use resistance level (195.00) when available
        assert tp == 195.00


class TestEdgeCases:
    def test_no_entry_price_returns_none(self):
        result = _adjust_entry_price({"stop_loss_price": 176}, current_price=185)
        assert result is None

    def test_no_stop_price_returns_none(self):
        result = _adjust_entry_price({"target_entry_price": 185}, current_price=185)
        assert result is None

    def test_zero_current_price_returns_none(self, thesis):
        result = _adjust_entry_price(thesis, current_price=0)
        assert result is None

    def test_no_tech_levels_still_works(self):
        thesis = {
            "target_entry_price": 185.50,
            "stop_loss_price": 176.23,
            "take_profit_price": 198.00,
            "key_technical_levels": {},
        }
        result = _adjust_entry_price(thesis, current_price=188.00)
        assert result is not None
        entry, stop, tp = result
        assert entry < 188.00  # Discount from current
        assert stop >= 176.23  # Floor preserved

    def test_no_take_profit_returns_none_tp(self):
        thesis = {
            "target_entry_price": 185.50,
            "stop_loss_price": 176.23,
            "take_profit_price": None,
            "key_technical_levels": {},
        }
        result = _adjust_entry_price(thesis, current_price=188.00)
        entry, stop, tp = result
        assert tp is None
