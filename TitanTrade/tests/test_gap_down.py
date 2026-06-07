"""Tests for gap-down protection.

All Alpaca calls mocked. Zero real orders.
"""

from __future__ import annotations

from unittest.mock import patch, call

import pytest

from titantrade.executor import check_gap_down_protection


class TestGapDownDetection:
    @patch("titantrade.executor._append_trade")
    @patch("titantrade.executor.place_market_sell", return_value={"id": "sell_1"})
    @patch("titantrade.executor._wait_for_order_canceled", return_value="canceled")
    @patch("titantrade.executor.cancel_order")
    @patch("titantrade.executor.get_open_orders")
    @patch("titantrade.executor.get_positions")
    def test_detects_gap_through_stop_limit(
        self, mock_pos, mock_orders, mock_cancel, mock_wait, mock_sell, mock_append,
        fake_config, tmp_state_dir,
    ):
        mock_pos.return_value = [
            {"symbol": "AAPL", "qty": "50", "current_price": "170.00"},
        ]
        mock_orders.return_value = [
            {
                "id": "stop_1",
                "type": "stop_limit",
                "side": "sell",
                "stop_price": "176.23",
                "limit_price": "174.47",
            },
        ]
        result = check_gap_down_protection(fake_config)
        assert len(result) == 1
        assert result[0]["trigger"] == "gap_down_protection"
        mock_cancel.assert_called_once_with("stop_1", fake_config)
        # FIX: must wait for the cancel to release the held qty BEFORE the
        # market sell, else the sell 403s "insufficient qty (available: 0)" —
        # the production bug where gap-down protection failed to fire on FCX.
        mock_wait.assert_called_once_with("stop_1", fake_config)
        mock_sell.assert_called_once_with("AAPL", 50, fake_config)

    @patch("titantrade.executor.place_market_sell")
    @patch("titantrade.executor.cancel_order")
    @patch("titantrade.executor.get_open_orders")
    @patch("titantrade.executor.get_positions")
    def test_no_gap_when_price_above_limit(
        self, mock_pos, mock_orders, mock_cancel, mock_sell,
        fake_config, tmp_state_dir,
    ):
        mock_pos.return_value = [
            {"symbol": "AAPL", "qty": "50", "current_price": "180.00"},
        ]
        mock_orders.return_value = [
            {
                "id": "stop_1",
                "type": "stop_limit",
                "side": "sell",
                "stop_price": "176.23",
                "limit_price": "174.47",
            },
        ]
        result = check_gap_down_protection(fake_config)
        assert len(result) == 0
        mock_cancel.assert_not_called()
        mock_sell.assert_not_called()

    @patch("titantrade.executor.get_open_orders", return_value=[])
    @patch("titantrade.executor.get_positions")
    def test_no_stop_orders_no_action(
        self, mock_pos, mock_orders, fake_config, tmp_state_dir,
    ):
        mock_pos.return_value = [
            {"symbol": "AAPL", "qty": "50", "current_price": "170.00"},
        ]
        result = check_gap_down_protection(fake_config)
        assert len(result) == 0

    @patch("titantrade.executor.get_positions", return_value=[])
    def test_no_positions_no_action(self, mock_pos, fake_config, tmp_state_dir):
        result = check_gap_down_protection(fake_config)
        assert len(result) == 0

    @patch("titantrade.executor.place_market_sell")
    @patch("titantrade.executor.cancel_order")
    @patch("titantrade.executor.get_open_orders")
    @patch("titantrade.executor.get_positions")
    def test_ignores_buy_stop_orders(
        self, mock_pos, mock_orders, mock_cancel, mock_sell,
        fake_config, tmp_state_dir,
    ):
        """Only sell-side stop-limits are gap protection targets."""
        mock_pos.return_value = [
            {"symbol": "AAPL", "qty": "50", "current_price": "170.00"},
        ]
        mock_orders.return_value = [
            {
                "id": "stop_buy",
                "type": "stop_limit",
                "side": "buy",
                "stop_price": "190.00",
                "limit_price": "192.00",
            },
        ]
        result = check_gap_down_protection(fake_config)
        assert len(result) == 0

    @patch("titantrade.executor._append_trade")
    @patch("titantrade.executor.place_market_sell", return_value={"id": "s1"})
    @patch("titantrade.executor.cancel_order")
    @patch("titantrade.executor.get_open_orders")
    @patch("titantrade.executor.get_positions")
    def test_uses_99pct_margin(
        self, mock_pos, mock_orders, mock_cancel, mock_sell, mock_append,
        fake_config, tmp_state_dir,
    ):
        """Price must be below limit * 0.99 to trigger, not just barely below."""
        mock_pos.return_value = [
            {"symbol": "AAPL", "qty": "50", "current_price": "173.50"},  # just below 174.47
        ]
        mock_orders.return_value = [
            {
                "id": "stop_1",
                "type": "stop_limit",
                "side": "sell",
                "stop_price": "176.23",
                "limit_price": "174.47",
            },
        ]
        # 174.47 * 0.99 = 172.72 — current 173.50 is above that threshold
        result = check_gap_down_protection(fake_config)
        assert len(result) == 0
