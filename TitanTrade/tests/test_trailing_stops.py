"""Tests for trailing stop mechanism.

All broker calls are mocked. Zero token spend, zero real orders.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch, call

import pytest

from titantrade.executor import (
    manage_trailing_stop,
    _load_trailing_state,
    _save_trailing_state,
    _cleanup_trailing_state,
)
from tests.conftest import write_state_file


@pytest.fixture
def position_up_6pct():
    """Position with 6% unrealized gain (above 5% trailing trigger)."""
    return {
        "symbol": "AAPL",
        "qty": "50",
        "avg_entry_price": "185.50",
        "current_price": "196.63",  # +6%
    }


@pytest.fixture
def position_up_3pct():
    """Position with 3% gain (below 5% trailing trigger)."""
    return {
        "symbol": "AAPL",
        "qty": "50",
        "avg_entry_price": "185.50",
        "current_price": "191.07",  # +3%
    }


@pytest.fixture
def thesis_with_stop():
    return {
        "ticker": "AAPL",
        "thesis": "BULLISH",
        "stop_loss_price": 176.23,
        "target_entry_price": 185.50,
    }


@pytest.fixture
def existing_stop_order():
    return {
        "id": "stop_order_1",
        "type": "stop_limit",
        "side": "sell",
        "stop_price": "176.23",
        "limit_price": "174.47",
    }


class TestTrailingStopActivation:
    @patch("titantrade.executor.place_native_stop_loss", return_value={"id": "new_stop"})
    @patch("titantrade.executor.cancel_order")
    @patch("titantrade.executor.get_position", return_value={"symbol": "AAPL", "qty": "50"})
    def test_activates_at_5pct_gain(
        self, mock_get_pos, mock_cancel, mock_place,
        position_up_6pct, thesis_with_stop, existing_stop_order,
        fake_config, tmp_state_dir,
    ):
        manage_trailing_stop(
            "AAPL", thesis_with_stop, position_up_6pct,
            [existing_stop_order], fake_config,
        )
        mock_cancel.assert_called_once_with("stop_order_1", fake_config)
        mock_place.assert_called_once()
        new_stop_price = mock_place.call_args[0][2]
        assert new_stop_price > 176.23  # Higher than original

    @patch("titantrade.executor.place_native_stop_loss")
    @patch("titantrade.executor.cancel_order")
    def test_does_not_activate_below_threshold(
        self, mock_cancel, mock_place,
        position_up_3pct, thesis_with_stop, existing_stop_order,
        fake_config, tmp_state_dir,
    ):
        manage_trailing_stop(
            "AAPL", thesis_with_stop, position_up_3pct,
            [existing_stop_order], fake_config,
        )
        mock_cancel.assert_not_called()
        mock_place.assert_not_called()

    @patch("titantrade.executor.place_native_stop_loss")
    @patch("titantrade.executor.cancel_order")
    def test_saves_state_even_when_inactive(
        self, mock_cancel, mock_place,
        position_up_3pct, thesis_with_stop, existing_stop_order,
        fake_config, tmp_state_dir,
    ):
        manage_trailing_stop(
            "AAPL", thesis_with_stop, position_up_3pct,
            [existing_stop_order], fake_config,
        )
        state = _load_trailing_state()
        assert "AAPL" in state
        assert state["AAPL"]["trailing_active"] is False


class TestTrailingStopRatchet:
    @patch("titantrade.executor.place_native_stop_loss", return_value={"id": "new"})
    @patch("titantrade.executor.cancel_order")
    @patch("titantrade.executor.get_position", return_value={"symbol": "AAPL", "qty": "50"})
    def test_trails_3pct_below_hwm(
        self, mock_get_pos, mock_cancel, mock_place,
        position_up_6pct, thesis_with_stop, existing_stop_order,
        fake_config, tmp_state_dir,
    ):
        manage_trailing_stop(
            "AAPL", thesis_with_stop, position_up_6pct,
            [existing_stop_order], fake_config,
        )
        new_stop = mock_place.call_args[0][2]
        hwm = 196.63
        expected = round(hwm * (1 - 0.03), 2)
        assert new_stop == expected

    @patch("titantrade.executor.place_native_stop_loss", return_value={"id": "new"})
    @patch("titantrade.executor.cancel_order")
    @patch("titantrade.executor.get_position", return_value={"symbol": "AAPL", "qty": "50"})
    def test_never_trails_below_entry(
        self, mock_get_pos, mock_cancel, mock_place,
        thesis_with_stop, existing_stop_order,
        fake_config, tmp_state_dir,
    ):
        """If the trail math produces a stop below entry, floor at entry * 1.005."""
        position = {
            "symbol": "AAPL",
            "qty": "50",
            "avg_entry_price": "185.50",
            "current_price": "195.00",  # ~5.1% gain, trail at 189.15 > entry
        }
        manage_trailing_stop(
            "AAPL", thesis_with_stop, position,
            [existing_stop_order], fake_config,
        )
        new_stop = mock_place.call_args[0][2]
        assert new_stop >= 185.50  # Never below entry

    @patch("titantrade.executor.place_native_stop_loss", return_value={"id": "new"})
    @patch("titantrade.executor.cancel_order")
    @patch("titantrade.executor.get_position", return_value={"symbol": "AAPL", "qty": "50"})
    def test_never_trails_below_original_stop(
        self, mock_get_pos, mock_cancel, mock_place,
        thesis_with_stop, existing_stop_order,
        fake_config, tmp_state_dir,
    ):
        manage_trailing_stop(
            "AAPL", thesis_with_stop,
            {"symbol": "AAPL", "qty": "50", "avg_entry_price": "185.50", "current_price": "196.63"},
            [existing_stop_order], fake_config,
        )
        new_stop = mock_place.call_args[0][2]
        assert new_stop >= thesis_with_stop["stop_loss_price"]

    @patch("titantrade.executor.place_native_stop_loss")
    @patch("titantrade.executor.cancel_order")
    def test_skips_if_existing_stop_already_higher(
        self, mock_cancel, mock_place,
        position_up_6pct, thesis_with_stop,
        fake_config, tmp_state_dir,
    ):
        """If the existing stop is already at or above the trailing level, don't replace."""
        high_stop_order = {
            "id": "stop_high",
            "type": "stop_limit",
            "side": "sell",
            "stop_price": "999.00",  # Already way above
            "limit_price": "998.00",
        }
        manage_trailing_stop(
            "AAPL", thesis_with_stop, position_up_6pct,
            [high_stop_order], fake_config,
        )
        mock_cancel.assert_not_called()
        mock_place.assert_not_called()


class TestTrailingStopState:
    @patch("titantrade.executor.place_native_stop_loss", return_value={"id": "new"})
    @patch("titantrade.executor.cancel_order")
    @patch("titantrade.executor.get_position", return_value={"symbol": "AAPL", "qty": "50"})
    def test_updates_hwm(
        self, mock_get_pos, mock_cancel, mock_place,
        position_up_6pct, thesis_with_stop, existing_stop_order,
        fake_config, tmp_state_dir,
    ):
        manage_trailing_stop(
            "AAPL", thesis_with_stop, position_up_6pct,
            [existing_stop_order], fake_config,
        )
        state = _load_trailing_state()
        assert state["AAPL"]["high_water_mark"] == 196.63
        assert state["AAPL"]["trailing_active"] is True

    def test_cleanup_removes_stale_tickers(self, tmp_state_dir):
        _save_trailing_state({
            "AAPL": {"trailing_active": True, "high_water_mark": 200},
            "TSLA": {"trailing_active": True, "high_water_mark": 300},
        })
        _cleanup_trailing_state({"AAPL"})  # Only AAPL still held
        state = _load_trailing_state()
        assert "AAPL" in state
        assert "TSLA" not in state

    def test_cleanup_noop_when_all_held(self, tmp_state_dir):
        _save_trailing_state({"AAPL": {"trailing_active": True}})
        _cleanup_trailing_state({"AAPL"})
        state = _load_trailing_state()
        assert "AAPL" in state
