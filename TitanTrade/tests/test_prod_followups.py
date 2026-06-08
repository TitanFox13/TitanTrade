"""Regression tests for issues found in the live deployment logs (post-refactor).

1. ABORT exit (`_handle_abort`) closed the position immediately after cancelling
   its protective stop — but the shares were still `held_for_orders`, so
   DELETE /positions 403'd ("available: 0"). Production: ANET ABORT failed on a
   -2.6% SPY stress day. Fix: wait for cancels to settle before closing.
2. The de-dup rename left `log_decision(..., extra={"atr": stock_atr})` pointing
   at the imported *function* (local was renamed to `atr`), so the JSON file
   handler raised "Object of type function is not JSON serializable". The
   console handler ignores `extra`, so the test suite was blind to it.

All Alpaca calls mocked — zero real orders.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from titantrade.executor import _handle_abort
from titantrade.entries import _handle_bullish_entry


class TestAbortCancelSettle:
    @patch("titantrade.executor._record_abort_cooldown")
    @patch("titantrade.executor._append_trade")
    @patch("titantrade.executor.close_position_at_market", return_value={"id": "close-1"})
    @patch("titantrade.executor.get_position")
    @patch("titantrade.executor._wait_for_order_canceled", return_value="canceled")
    @patch("titantrade.executor.cancel_order")
    @patch("titantrade.executor.get_open_orders")
    def test_waits_for_cancel_before_close(
        self, mock_orders, mock_cancel, mock_wait, mock_pos, mock_close,
        mock_append, mock_cooldown, fake_config, tmp_state_dir,
    ):
        # 85 shares held by a resting stop — the ANET scenario.
        mock_orders.return_value = [{"id": "stop-85", "type": "stop_limit", "side": "sell"}]
        mock_pos.return_value = {"symbol": "ANET", "qty": "85", "current_price": "150.00"}
        sentry = {"signal": "ABORT", "reasoning": "stress", "price_concern": True}

        trade = _handle_abort("ANET", sentry, fake_config)

        # Cancelled the stop AND polled it to a terminal state BEFORE closing,
        # so the close isn't rejected for held qty.
        mock_cancel.assert_called_once_with("stop-85", fake_config)
        mock_wait.assert_called_once_with("stop-85", fake_config)
        mock_close.assert_called_once()
        assert trade is not None and trade["trigger"] == "sentry_abort"


class TestEntryLogExtraSerializable:
    @patch("titantrade.daily_sentry._fetch_current_price", return_value=185.0)
    @patch("titantrade.entries.log_decision")
    @patch("titantrade.entries.place_bracket_order", return_value={"id": "br"})
    @patch("titantrade.entries.get_open_orders", return_value=[])
    def test_entry_log_extra_is_json_serializable(
        self, mock_orders, mock_bracket, mock_logdec, mock_price,
        fake_config, bullish_thesis, sample_positions, tmp_state_dir, monkeypatch,
    ):
        monkeypatch.setattr("titantrade.risk_manager.get_stock_sector", lambda t: "Technology")
        bundle = {"stocks": {"AAPL": {"technical_indicators": {"price_vs_sma": {}}, "atr_14": 3.0}}}

        result = _handle_bullish_entry(
            ticker="AAPL", thesis=bullish_thesis,
            portfolio_value=100_000, cash_balance=50_000,
            positions=sample_positions, data_bundle=bundle,
            sentry=None, cfg=fake_config,
        )
        assert result is not None  # bracket placed
        assert mock_logdec.called
        extra = mock_logdec.call_args.kwargs["extra"]
        # The exact failure: a function in extra -> JSONFormatter json.dumps raises.
        json.dumps(extra)
        assert not callable(extra["atr"])
        assert extra["atr"] == 3.0
