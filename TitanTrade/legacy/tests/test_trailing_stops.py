"""Tests for trailing stop mechanism.

All broker calls are mocked. Zero token spend, zero real orders.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch, call

import pytest

from titantrade.positions import manage_trailing_stop
from titantrade.trailing_state import (
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
    @patch("titantrade.positions.place_native_stop_loss", return_value={"id": "new_stop"})
    @patch("titantrade.positions.cancel_order")
    @patch("titantrade.positions.get_position", return_value={"symbol": "AAPL", "qty": "50"})
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

    @patch("titantrade.positions.place_native_stop_loss")
    @patch("titantrade.positions.cancel_order")
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

    @patch("titantrade.positions.place_native_stop_loss")
    @patch("titantrade.positions.cancel_order")
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
    @patch("titantrade.positions.place_native_stop_loss", return_value={"id": "new"})
    @patch("titantrade.positions.cancel_order")
    @patch("titantrade.positions.get_position", return_value={"symbol": "AAPL", "qty": "50"})
    def test_trails_pct_fallback_when_no_atr(
        self, mock_get_pos, mock_cancel, mock_place,
        position_up_6pct, thesis_with_stop, existing_stop_order,
        fake_config, tmp_state_dir,
    ):
        """When ATR is not supplied (or zero), the trailing distance falls
        back to the % trail. Default is now 5% (was 3%) to give noise room.
        """
        manage_trailing_stop(
            "AAPL", thesis_with_stop, position_up_6pct,
            [existing_stop_order], fake_config,
            stock_atr=None,  # explicit fallback path
        )
        new_stop = mock_place.call_args[0][2]
        hwm = 196.63
        expected = round(hwm * (1 - fake_config.trading.trailing_distance_pct), 2)
        assert new_stop == expected

    @patch("titantrade.positions.place_native_stop_loss", return_value={"id": "new"})
    @patch("titantrade.positions.cancel_order")
    @patch("titantrade.positions.get_position", return_value={"symbol": "AAPL", "qty": "50"})
    def test_trails_atr_distance_when_atr_supplied(
        self, mock_get_pos, mock_cancel, mock_place,
        position_up_6pct, thesis_with_stop, existing_stop_order,
        fake_config, tmp_state_dir,
    ):
        """ATR-based trailing: stop sits trailing_atr_multiplier x ATR below
        HWM. ATR=$2 (chosen so the ATR trail is the binding constraint, clear
        of the breakeven floor) and HWM=$196.63 → stop at HWM - mult*2.
        """
        atr = 2.0
        manage_trailing_stop(
            "AAPL", thesis_with_stop, position_up_6pct,
            [existing_stop_order], fake_config,
            stock_atr=atr,
        )
        new_stop = mock_place.call_args[0][2]
        hwm = 196.63
        expected = round(hwm - atr * fake_config.trading.trailing_atr_multiplier, 2)
        assert new_stop == expected

    @patch("titantrade.positions.place_native_stop_loss", return_value={"id": "new"})
    @patch("titantrade.positions.cancel_order")
    @patch("titantrade.positions.get_position", return_value={"symbol": "AAPL", "qty": "50"})
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

    @patch("titantrade.positions.place_native_stop_loss", return_value={"id": "new"})
    @patch("titantrade.positions.cancel_order")
    @patch("titantrade.positions.get_position", return_value={"symbol": "AAPL", "qty": "50"})
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

    @patch("titantrade.positions.place_native_stop_loss")
    @patch("titantrade.positions.cancel_order")
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
    @patch("titantrade.positions.place_native_stop_loss", return_value={"id": "new"})
    @patch("titantrade.positions.cancel_order")
    @patch("titantrade.positions.get_position", return_value={"symbol": "AAPL", "qty": "50"})
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


class TestTrancheTpFirstTake:
    """When gain reaches tp1_trigger_fraction of upside-to-TP, sell a partial
    chunk (tp1_fraction) and raise the stop to breakeven. This is what stops
    25% winners from giving back gains on noise.
    """

    @pytest.fixture
    def position_at_tp1(self):
        # entry $100, tp $120 → upside $20. tp1_trigger 50% → trigger at $110.
        return {
            "symbol": "FOO",
            "qty": "30",  # 30 shares so tp1_fraction=1/3 takes a clean 10
            "avg_entry_price": "100.00",
            "current_price": "111.00",  # past TP1 trigger
        }

    @pytest.fixture
    def thesis_with_tp(self):
        return {
            "ticker": "FOO",
            "thesis": "BULLISH",
            "stop_loss_price": 92.0,
            "target_entry_price": 100.0,
            "take_profit_price": 120.0,
        }

    @patch("titantrade.positions._wait_for_order_canceled", return_value="filled")
    @patch("titantrade.positions.time.sleep", return_value=None)
    @patch("titantrade.positions.place_native_stop_loss", return_value={"id": "new-stop"})
    @patch("titantrade.positions.place_market_sell", return_value={"id": "tp1-sell"})
    @patch("titantrade.positions.cancel_all_orders_for_ticker", return_value=1)
    @patch("titantrade.positions.get_position")
    @patch("titantrade.positions.get_open_orders", return_value=[])
    def test_partial_sell_and_breakeven_stop(
        self,
        mock_get_open, mock_get_pos, mock_cancel_all, mock_market_sell,
        mock_place_stop, mock_sleep, mock_wait,
        position_at_tp1, thesis_with_tp, fake_config, tmp_state_dir,
    ):
        # After partial sell, position has 20 shares remaining
        mock_get_pos.return_value = {"symbol": "FOO", "qty": "20", "avg_entry_price": "100.00"}

        manage_trailing_stop(
            "FOO", thesis_with_tp, position_at_tp1, [], fake_config,
            stock_atr=2.0,
        )

        # Partial sell happened
        mock_market_sell.assert_called_once()
        sell_args = mock_market_sell.call_args.args
        assert sell_args[0] == "FOO"
        assert sell_args[1] == 10  # 30 * 0.333 = 10
        # FIX: the breakeven stop is sized only AFTER the partial sell has been
        # polled to a terminal ('filled') state — the position read that sizes
        # the stop must not race the fill (the FCX bare-position bug).
        mock_wait.assert_called_once_with("tp1-sell", fake_config)
        # Stop was re-placed at breakeven on the remaining 20 shares
        stop_calls = mock_place_stop.call_args_list
        assert len(stop_calls) >= 1
        breakeven_call = stop_calls[0]
        assert breakeven_call.args[0] == "FOO"
        assert breakeven_call.args[1] == 20.0
        # entry * 1.005 = 100.50
        assert breakeven_call.args[2] == pytest.approx(100.50, abs=0.01)
        # State tracks the TP1 take so it doesn't fire twice
        state = _load_trailing_state()
        assert state["FOO"]["tp1_taken"] is True

    @patch("titantrade.positions.place_native_stop_loss", return_value={"id": "new-stop"})
    @patch("titantrade.positions.place_market_sell")
    @patch("titantrade.positions.cancel_all_orders_for_ticker")
    @patch("titantrade.positions.get_position")
    def test_tp1_does_not_fire_below_trigger(
        self,
        mock_get_pos, mock_cancel_all, mock_market_sell, mock_place_stop,
        thesis_with_tp, fake_config, tmp_state_dir,
    ):
        # At entry $100, tp $120 → TP1 trigger = $110. At $108 we should NOT fire.
        pos = {
            "symbol": "FOO", "qty": "30",
            "avg_entry_price": "100.00", "current_price": "108.00",
        }
        manage_trailing_stop("FOO", thesis_with_tp, pos, [], fake_config, stock_atr=2.0)
        mock_market_sell.assert_not_called()

    @patch("titantrade.positions.time.sleep", return_value=None)
    @patch("titantrade.positions.place_native_stop_loss", return_value={"id": "new-stop"})
    @patch("titantrade.positions.place_market_sell", return_value={"id": "tp1-sell"})
    @patch("titantrade.positions.cancel_all_orders_for_ticker", return_value=1)
    @patch("titantrade.positions.get_position")
    @patch("titantrade.positions.get_open_orders", return_value=[])
    def test_tp1_only_fires_once(
        self,
        mock_get_open, mock_get_pos, mock_cancel_all, mock_market_sell,
        mock_place_stop, mock_sleep,
        position_at_tp1, thesis_with_tp, fake_config, tmp_state_dir,
    ):
        # Seed state as if TP1 already fired
        _save_trailing_state({"FOO": {"tp1_taken": True, "high_water_mark": 111.0}})

        manage_trailing_stop(
            "FOO", thesis_with_tp, position_at_tp1, [], fake_config,
            stock_atr=2.0,
        )
        # No second partial sell
        mock_market_sell.assert_not_called()
