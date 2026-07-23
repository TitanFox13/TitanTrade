"""Tests for gap-down protection.

All Alpaca calls mocked. Zero real orders.
"""

from __future__ import annotations

from unittest.mock import patch

from titantrade.executor import check_gap_down_protection


class TestGapDownDetection:
    @patch("titantrade.daily_sentry._fetch_current_price", return_value=169.0)
    @patch("titantrade.protection._append_trade")
    @patch("titantrade.protection.place_market_sell", return_value={"id": "sell_1"})
    @patch("titantrade.protection._wait_for_order_canceled", return_value="canceled")
    @patch("titantrade.protection.cancel_order")
    @patch("titantrade.protection.get_open_orders")
    @patch("titantrade.protection.get_positions")
    def test_detects_gap_through_stop_limit(
        self, mock_pos, mock_orders, mock_cancel, mock_wait, mock_sell, mock_append,
        mock_fetch, fake_config, tmp_state_dir,
    ):
        # Live quote (169) confirms the gap (below stop 176.23) → sell fires.
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

    @patch("titantrade.protection.place_market_sell")
    @patch("titantrade.protection.cancel_order")
    @patch("titantrade.protection.get_open_orders")
    @patch("titantrade.protection.get_positions")
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

    @patch("titantrade.protection.get_open_orders", return_value=[])
    @patch("titantrade.protection.get_positions")
    def test_no_stop_orders_no_action(
        self, mock_pos, mock_orders, fake_config, tmp_state_dir,
    ):
        mock_pos.return_value = [
            {"symbol": "AAPL", "qty": "50", "current_price": "170.00"},
        ]
        result = check_gap_down_protection(fake_config)
        assert len(result) == 0

    @patch("titantrade.protection.get_positions", return_value=[])
    def test_no_positions_no_action(self, mock_pos, fake_config, tmp_state_dir):
        result = check_gap_down_protection(fake_config)
        assert len(result) == 0

    @patch("titantrade.protection.place_market_sell")
    @patch("titantrade.protection.cancel_order")
    @patch("titantrade.protection.get_open_orders")
    @patch("titantrade.protection.get_positions")
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

    @patch("titantrade.protection._append_trade")
    @patch("titantrade.protection.place_market_sell", return_value={"id": "s1"})
    @patch("titantrade.protection.cancel_order")
    @patch("titantrade.protection.get_open_orders")
    @patch("titantrade.protection.get_positions")
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


class TestGapDownLiveQuoteCrossCheck:
    """Regression: gap-down protection must cross-check the LIVE market quote
    before liquidating, so a stale/glitched position mark (e.g. Alpaca paper's
    phantom-split on CRWD — position marked $196 while the market traded $772)
    can't trip the gate and sell a healthy position. A missing quote must still
    fall through to the sell (never weaken protection).
    """

    _ORDER = {
        "id": "stop_1", "type": "stop_limit", "side": "sell",
        "stop_price": "661.00", "limit_price": "654.39",
    }

    @patch("titantrade.daily_sentry._fetch_current_price", return_value=772.6)
    @patch("titantrade.protection._append_trade")
    @patch("titantrade.protection.place_market_sell")
    @patch("titantrade.protection.cancel_order")
    @patch("titantrade.protection.get_open_orders")
    @patch("titantrade.protection.get_positions")
    def test_skips_sell_when_live_quote_contradicts_glitched_mark(
        self, mock_pos, mock_orders, mock_cancel, mock_sell, mock_append,
        mock_fetch, fake_config, tmp_state_dir,
    ):
        # Position mark $196 (glitched, below limit) but market $772.6 >= stop.
        mock_pos.return_value = [
            {"symbol": "CRWD", "qty": "15", "current_price": "196.16"},
        ]
        mock_orders.return_value = [self._ORDER]
        result = check_gap_down_protection(fake_config)
        assert result == []                 # no liquidation on a bad mark
        mock_cancel.assert_not_called()
        mock_sell.assert_not_called()

    @patch("titantrade.daily_sentry._fetch_current_price", return_value=610.0)
    @patch("titantrade.protection._append_trade")
    @patch("titantrade.protection.place_market_sell", return_value={"id": "s1"})
    @patch("titantrade.protection._wait_for_order_canceled", return_value="canceled")
    @patch("titantrade.protection.cancel_order")
    @patch("titantrade.protection.get_open_orders")
    @patch("titantrade.protection.get_positions")
    def test_sells_when_live_quote_confirms_gap(
        self, mock_pos, mock_orders, mock_cancel, mock_wait, mock_sell, mock_append,
        mock_fetch, fake_config, tmp_state_dir,
    ):
        # Live quote $610 < stop $661 → a REAL gap: protection must still fire.
        mock_pos.return_value = [
            {"symbol": "CRWD", "qty": "15", "current_price": "605.00"},
        ]
        mock_orders.return_value = [self._ORDER]
        result = check_gap_down_protection(fake_config)
        assert len(result) == 1
        assert result[0]["trigger"] == "gap_down_protection"
        mock_sell.assert_called_once_with("CRWD", 15, fake_config)

    @patch("titantrade.daily_sentry._fetch_current_price", return_value=None)
    @patch("titantrade.protection._append_trade")
    @patch("titantrade.protection.place_market_sell", return_value={"id": "s1"})
    @patch("titantrade.protection._wait_for_order_canceled", return_value="canceled")
    @patch("titantrade.protection.cancel_order")
    @patch("titantrade.protection.get_open_orders")
    @patch("titantrade.protection.get_positions")
    def test_sells_when_live_quote_unavailable(
        self, mock_pos, mock_orders, mock_cancel, mock_wait, mock_sell, mock_append,
        mock_fetch, fake_config, tmp_state_dir,
    ):
        # Quote fetch returns None (feed down) → fall through to the sell so a
        # genuine unprotected position is never left bare.
        mock_pos.return_value = [
            {"symbol": "CRWD", "qty": "15", "current_price": "605.00"},
        ]
        mock_orders.return_value = [self._ORDER]
        result = check_gap_down_protection(fake_config)
        assert len(result) == 1
        mock_sell.assert_called_once_with("CRWD", 15, fake_config)


class TestGapDownSplitGuard:
    """Regression: the 2026-07-02 CRWD incident. The market genuinely traded
    at the post-split price ($192.67) — so the live-quote cross-check (ADR 053)
    correctly confirmed the gap — but the position basis and the $661 stop were
    still pre-split: Alpaca paper applied the position adjustment three trading
    days late, and the gate sold a healthy position at the artificial bottom.
    For gaps deeper than SPLIT_SUSPECT_GAP_PCT below the stop, protection must
    consult the corporate-actions feed and skip when a recent split explains
    the move. Feed errors / no announcement must still fall through to the
    sell (a real crash must never be left unprotected).
    """

    _ORDER = {
        "id": "stop_1", "type": "stop_limit", "side": "sell",
        "stop_price": "661.00", "limit_price": "654.39",
    }
    _SPLIT_ANN = {
        "id": "ann_1", "ca_type": "split", "ca_sub_type": "stock_split",
        "initiating_symbol": "CRWD", "old_rate": "1", "new_rate": "4",
        "ex_date": "2026-07-02",
    }

    @patch("titantrade.protection.get_recent_split_announcements")
    @patch("titantrade.daily_sentry._fetch_current_price", return_value=192.67)
    @patch("titantrade.protection._append_trade")
    @patch("titantrade.protection.place_market_sell")
    @patch("titantrade.protection.cancel_order")
    @patch("titantrade.protection.get_open_orders")
    @patch("titantrade.protection.get_positions")
    def test_skips_sell_when_split_announced(
        self, mock_pos, mock_orders, mock_cancel, mock_sell, mock_append,
        mock_fetch, mock_splits, fake_config, tmp_state_dir,
    ):
        # Live quote confirms $192.67 < stop $661 (71% gap) but a 4:1 split
        # announcement explains it → no liquidation.
        mock_splits.return_value = [self._SPLIT_ANN]
        mock_pos.return_value = [
            {"symbol": "CRWD", "qty": "15", "current_price": "192.67"},
        ]
        mock_orders.return_value = [self._ORDER]
        result = check_gap_down_protection(fake_config)
        assert result == []
        mock_cancel.assert_not_called()
        mock_sell.assert_not_called()
        mock_splits.assert_called_once_with("CRWD", fake_config)

    @patch("titantrade.protection.get_recent_split_announcements", return_value=[])
    @patch("titantrade.daily_sentry._fetch_current_price", return_value=192.67)
    @patch("titantrade.protection._append_trade")
    @patch("titantrade.protection.place_market_sell", return_value={"id": "s1"})
    @patch("titantrade.protection._wait_for_order_canceled", return_value="canceled")
    @patch("titantrade.protection.cancel_order")
    @patch("titantrade.protection.get_open_orders")
    @patch("titantrade.protection.get_positions")
    def test_sells_deep_gap_with_no_announcement(
        self, mock_pos, mock_orders, mock_cancel, mock_wait, mock_sell, mock_append,
        mock_fetch, mock_splits, fake_config, tmp_state_dir,
    ):
        # Deep gap but the feed shows no split → treat as a real crash: sell.
        mock_pos.return_value = [
            {"symbol": "CRWD", "qty": "15", "current_price": "192.67"},
        ]
        mock_orders.return_value = [self._ORDER]
        result = check_gap_down_protection(fake_config)
        assert len(result) == 1
        mock_sell.assert_called_once_with("CRWD", 15, fake_config)

    @patch(
        "titantrade.protection.get_recent_split_announcements",
        side_effect=RuntimeError("announcements feed down"),
    )
    @patch("titantrade.daily_sentry._fetch_current_price", return_value=192.67)
    @patch("titantrade.protection._append_trade")
    @patch("titantrade.protection.place_market_sell", return_value={"id": "s1"})
    @patch("titantrade.protection._wait_for_order_canceled", return_value="canceled")
    @patch("titantrade.protection.cancel_order")
    @patch("titantrade.protection.get_open_orders")
    @patch("titantrade.protection.get_positions")
    def test_sells_when_announcements_feed_errors(
        self, mock_pos, mock_orders, mock_cancel, mock_wait, mock_sell, mock_append,
        mock_fetch, mock_splits, fake_config, tmp_state_dir,
    ):
        # Feed error must not weaken protection — fall through to the sell.
        mock_pos.return_value = [
            {"symbol": "CRWD", "qty": "15", "current_price": "192.67"},
        ]
        mock_orders.return_value = [self._ORDER]
        result = check_gap_down_protection(fake_config)
        assert len(result) == 1
        mock_sell.assert_called_once_with("CRWD", 15, fake_config)

    @patch("titantrade.protection.get_recent_split_announcements")
    @patch("titantrade.daily_sentry._fetch_current_price", return_value=610.0)
    @patch("titantrade.protection._append_trade")
    @patch("titantrade.protection.place_market_sell", return_value={"id": "s1"})
    @patch("titantrade.protection._wait_for_order_canceled", return_value="canceled")
    @patch("titantrade.protection.cancel_order")
    @patch("titantrade.protection.get_open_orders")
    @patch("titantrade.protection.get_positions")
    def test_moderate_gap_skips_split_check(
        self, mock_pos, mock_orders, mock_cancel, mock_wait, mock_sell, mock_append,
        mock_fetch, mock_splits, fake_config, tmp_state_dir,
    ):
        # $610 vs $661 stop is a 7.7% gap — an ordinary gap-down, no split
        # plausible. The announcements feed must not even be consulted.
        mock_pos.return_value = [
            {"symbol": "CRWD", "qty": "15", "current_price": "605.00"},
        ]
        mock_orders.return_value = [self._ORDER]
        result = check_gap_down_protection(fake_config)
        assert len(result) == 1
        mock_splits.assert_not_called()
        mock_sell.assert_called_once_with("CRWD", 15, fake_config)

    @patch("titantrade.protection.get_recent_split_announcements")
    @patch("titantrade.daily_sentry._fetch_current_price", return_value=None)
    @patch("titantrade.protection._append_trade")
    @patch("titantrade.protection.place_market_sell")
    @patch("titantrade.protection.cancel_order")
    @patch("titantrade.protection.get_open_orders")
    @patch("titantrade.protection.get_positions")
    def test_split_check_uses_position_mark_when_quote_unavailable(
        self, mock_pos, mock_orders, mock_cancel, mock_sell, mock_append,
        mock_fetch, mock_splits, fake_config, tmp_state_dir,
    ):
        # No live quote, but the position mark itself shows a 71% gap and a
        # split is announced → still skip (the mark is the split artifact).
        mock_splits.return_value = [self._SPLIT_ANN]
        mock_pos.return_value = [
            {"symbol": "CRWD", "qty": "15", "current_price": "192.67"},
        ]
        mock_orders.return_value = [self._ORDER]
        result = check_gap_down_protection(fake_config)
        assert result == []
        mock_sell.assert_not_called()
