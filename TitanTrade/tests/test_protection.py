"""Orphan close (plan-based) and the settled close. Gap-down protection has
its own file. All broker calls mocked."""

from __future__ import annotations

import json
from unittest.mock import patch

from titantrade.protection import close_orphaned_positions, close_position_settled


def _plan(state_dir, *tickers):
    (state_dir / "plan.json").write_text(json.dumps({"items": [{"ticker": t, "action": "HOLD"} for t in tickers]}))


class TestOrphanClose:
    @patch("titantrade.protection.close_position_settled", return_value={"ticker": "TSLA", "action": "SELL", "trigger": "orphan_close"})
    @patch("titantrade.protection.get_positions")
    def test_closes_names_without_an_item_and_keeps_the_rest(self, mock_pos, mock_close, fake_config, tmp_state_dir):
        _plan(tmp_state_dir, "AAPL")
        mock_pos.return_value = [
            {"symbol": "AAPL", "qty": "50"}, {"symbol": "TSLA", "qty": "30"},
            {"symbol": "SPY", "qty": "40"}, {"symbol": "GE", "qty": "0"},
        ]
        result = close_orphaned_positions(fake_config)
        assert [r["ticker"] for r in result] == ["TSLA"]
        mock_close.assert_called_once()
        assert mock_close.call_args.args[0] == "TSLA"

    @patch("titantrade.protection.close_position_settled", side_effect=RuntimeError("broker down"))
    @patch("titantrade.protection.get_positions", return_value=[{"symbol": "TSLA", "qty": "30"}])
    def test_failed_close_is_logged_and_retried_next_run(self, mock_pos, mock_close, fake_config, tmp_state_dir):
        _plan(tmp_state_dir)
        assert close_orphaned_positions(fake_config) == []

    @patch("titantrade.protection.get_positions", return_value=[])
    def test_no_positions(self, mock_pos, fake_config, tmp_state_dir):
        assert close_orphaned_positions(fake_config) == []


class TestSettledClose:
    @patch("titantrade.protection.close_position_at_market", return_value={"id": "c1"})
    @patch("titantrade.protection.get_position", return_value={"symbol": "FCX", "qty": "109", "current_price": "73.5"})
    @patch("titantrade.protection._wait_for_order_canceled", return_value="canceled")
    @patch("titantrade.protection.cancel_order")
    @patch("titantrade.protection.get_open_orders", return_value=[{"id": "stop-1", "type": "stop_limit", "side": "sell", "stop_price": "71.4"}])
    def test_cancels_waits_then_sells(self, mock_oo, mock_cancel, mock_wait, mock_pos, mock_close, fake_config, tmp_state_dir):
        trade = close_position_settled("FCX", fake_config, trigger="orphan_close", reason="legacy")
        mock_cancel.assert_called_once_with("stop-1", fake_config)
        mock_wait.assert_called_once_with("stop-1", fake_config)
        mock_close.assert_called_once()
        assert trade["ticker"] == "FCX" and trade["shares"] == 109.0 and trade["trigger"] == "orphan_close"

    @patch("titantrade.protection.place_native_stop_loss")
    @patch("titantrade.protection.close_position_at_market", side_effect=RuntimeError("403"))
    @patch("titantrade.protection.get_position", return_value={"symbol": "FCX", "qty": "109", "current_price": "73.5"})
    @patch("titantrade.protection._wait_for_order_canceled", return_value="canceled")
    @patch("titantrade.protection.cancel_order")
    @patch("titantrade.protection.get_open_orders", return_value=[{"id": "stop-1", "type": "stop_limit", "side": "sell", "stop_price": "71.4"}])
    def test_failed_sell_restores_the_stop(self, mock_oo, mock_cancel, mock_wait, mock_pos, mock_close, mock_stop, fake_config, tmp_state_dir):
        assert close_position_settled("FCX", fake_config, trigger="target", reason="r") is None
        mock_stop.assert_called_once_with("FCX", 109.0, 71.4, fake_config)
