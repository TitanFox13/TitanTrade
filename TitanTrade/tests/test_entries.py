"""Entries: near-market bracket through the gates, cooldown, committed cash,
stop-out cooldown scan, fill reconcile.
All broker calls mocked."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from titantrade.entries import (
    _ensure_gtc_stop_on_fill, handle_entry, open_buy_commitment,
    record_stop_out_cooldowns,
)


def _resp(data):
    m = MagicMock()
    m.json.return_value = data
    return m


def _item(ticker="AAA", entry=100.0):
    return {"ticker": ticker, "action": "NEW", "entry_price": entry, "stop_price": entry * 0.88,
            "target_price": entry * 1.2, "dip_pct": 0.11, "reason": "dip", "sector": "Technology"}


@pytest.fixture(autouse=True)
def _sector(monkeypatch):
    monkeypatch.setattr("titantrade.risk_manager.get_stock_sector", lambda t: "ETF" if t == "SPY" else "Technology")


class TestHandleEntry:
    @patch("titantrade.entries.get_open_orders", return_value=[])
    @patch("titantrade.entries.place_bracket_order", return_value={"id": "b1"})
    @patch("titantrade.entries.get_latest_price", return_value=100.0)
    def test_places_one_bracket_at_near_market_with_pct_levels(self, mock_price, mock_bracket, mock_oo, fake_config, tmp_state_dir):
        trade = handle_entry(_item(entry=98.0), portfolio_value=100_000, cash_balance=60_000, positions=[], data_bundle={}, cfg=fake_config)
        assert trade and trade["action"] == "BUY" and trade["trigger"] == "entry"
        kw = mock_bracket.call_args.kwargs
        assert kw["entry_limit_price"] == 100.3                       # live mark × 1.003, not the plan's 98
        assert kw["stop_loss_price"] == round(100.3 * 0.88, 2)
        assert kw["take_profit_price"] == round(100.3 * 1.20, 2)
        assert kw["qty"] == 249.0                                      # 25% of $100k at $100.30
        assert trade["stop_price"] == kw["stop_loss_price"] and trade["target_price"] == kw["take_profit_price"]
        log = json.loads((tmp_state_dir / "trade_log.json").read_text())["trades"]
        assert log[-1]["ticker"] == "AAA"

    @patch("titantrade.entries.get_open_orders", return_value=[])
    @patch("titantrade.entries.place_bracket_order")
    @patch("titantrade.entries.get_latest_price", return_value=100.0)
    def test_blocked_entry_records_a_near_miss(self, mock_price, mock_bracket, mock_oo, fake_config, tmp_state_dir):
        bundle = {"stocks": {"AAA": {"earnings": {"is_blocked": True}}}}
        assert handle_entry(_item(), portfolio_value=100_000, cash_balance=60_000, positions=[], data_bundle=bundle, cfg=fake_config) is None
        mock_bracket.assert_not_called()
        nm = json.loads((tmp_state_dir / "near_misses.json").read_text())["near_misses"]
        assert nm[-1]["ticker"] == "AAA" and nm[-1]["failed_gates"] == ["earnings"]

    @patch("titantrade.entries.place_bracket_order")
    @patch("titantrade.entries.get_open_orders")
    @patch("titantrade.entries.get_latest_price", return_value=100.0)
    def test_committed_cash_blocks(self, mock_price, mock_oo, mock_bracket, fake_config, tmp_state_dir):
        mock_oo.return_value = [{"symbol": "NVDA", "side": "buy", "qty": "160", "limit_price": "300.00"}]
        assert handle_entry(_item(), portfolio_value=100_000, cash_balance=50_000, positions=[], data_bundle={}, cfg=fake_config) is None
        mock_bracket.assert_not_called()

    @patch("titantrade.entries.get_open_orders", return_value=[])
    @patch("titantrade.entries.place_bracket_order", return_value={"id": "b1"})
    @patch("titantrade.entries.get_latest_price")
    def test_cooldown_blocks_then_override_after_recovery(self, mock_price, mock_bracket, mock_oo, fake_config, tmp_state_dir):
        from titantrade.cooldown import _record_stop_out_cooldown
        filled = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
        _record_stop_out_cooldown("AAA", filled, "stop-loss exit", exit_price=100.0)
        mock_price.return_value = 100.5                                # +0.5%: still cooling down
        assert handle_entry(_item(), portfolio_value=100_000, cash_balance=60_000, positions=[], data_bundle={}, cfg=fake_config) is None
        mock_bracket.assert_not_called()
        mock_price.return_value = 101.5                                # +1.5%: override
        with patch("titantrade.notifier.send_discord"):
            trade = handle_entry(_item(), portfolio_value=100_000, cash_balance=60_000, positions=[], data_bundle={}, cfg=fake_config)
        assert trade and mock_bracket.called

    @patch("titantrade.entries.get_open_orders", return_value=[])
    @patch("titantrade.entries.place_bracket_order")
    @patch("titantrade.entries.get_latest_price", return_value=None)
    def test_no_price_and_no_plan_entry_skips(self, mock_price, mock_bracket, mock_oo, fake_config, tmp_state_dir):
        item = {**_item(), "entry_price": None}
        assert handle_entry(item, portfolio_value=100_000, cash_balance=60_000, positions=[], data_bundle={}, cfg=fake_config) is None
        mock_bracket.assert_not_called()


class TestOpenBuyCommitment:
    @patch("titantrade.entries.get_open_orders")
    def test_sums_pending_buys_and_excludes_ticker(self, mock_orders, fake_config):
        mock_orders.return_value = [
            {"symbol": "GE", "side": "buy", "qty": "31", "limit_price": "318.00"},
            {"symbol": "FCX", "side": "buy", "qty": "155", "limit_price": "65.00"},
            {"symbol": "AAPL", "side": "sell", "qty": "10", "limit_price": "200.00"},
        ]
        assert open_buy_commitment(fake_config) == pytest.approx(31 * 318.0 + 155 * 65.0)
        assert open_buy_commitment(fake_config, exclude_ticker="GE") == pytest.approx(155 * 65.0)


class TestStopOutCooldownScan:
    def _closed(self, **o):
        base = {"symbol": "DVN", "side": "sell", "type": "stop_limit", "status": "filled",
                "filled_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
                "filled_avg_price": "43.42", "stop_price": "43.50"}
        base.update(o)
        return base

    @patch("titantrade.entries.fetch_with_retry")
    def test_records_fill_time_and_price_idempotently(self, mock_fetch, fake_config, tmp_state_dir):
        from titantrade.cooldown import _is_in_cooldown, cooldown_exit_price
        mock_fetch.return_value = _resp([self._closed()])
        assert record_stop_out_cooldowns(fake_config) == 1
        in_cd, hours = _is_in_cooldown("DVN")
        assert in_cd and 1.5 < hours < 2.5
        assert cooldown_exit_price("DVN") == pytest.approx(43.42)
        assert record_stop_out_cooldowns(fake_config) == 0        # same fill → no re-stamp

    @patch("titantrade.entries.fetch_with_retry")
    def test_handles_z_timestamps_and_ignores_non_stop_fills(self, mock_fetch, fake_config, tmp_state_dir):
        from titantrade.cooldown import _is_in_cooldown
        z = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
        old = (datetime.now(timezone.utc) - timedelta(hours=100)).isoformat()
        mock_fetch.return_value = _resp([
            self._closed(filled_at=z),
            self._closed(symbol="URI", filled_at=old), self._closed(symbol="LLY", type="market"),
            self._closed(symbol="GE", side="buy"), self._closed(symbol="FCX", status="canceled", filled_at=None),
        ])
        assert record_stop_out_cooldowns(fake_config) == 1
        assert _is_in_cooldown("DVN")[0]
        for t in ("URI", "LLY", "GE", "FCX"):
            assert _is_in_cooldown(t) == (False, 0.0)

    @patch("titantrade.entries.fetch_with_retry", side_effect=RuntimeError("api down"))
    def test_scan_failure_returns_zero(self, mock_fetch, fake_config, tmp_state_dir):
        assert record_stop_out_cooldowns(fake_config) == 0


@pytest.mark.real_stop_reconcile
class TestEnsureGtcStopOnFill:
    @patch("titantrade.entries.place_native_stop_loss", return_value={"id": "gtc"})
    @patch("titantrade.entries._wait_for_order_canceled", return_value="canceled")
    @patch("titantrade.entries.cancel_order")
    @patch("titantrade.entries.get_open_orders")
    @patch("titantrade.entries.get_position", return_value={"symbol": "AAPL", "qty": "10"})
    @patch("titantrade.entries.get_order", return_value={"status": "filled", "filled_avg_price": "100.25"})
    def test_fill_replaces_held_leg_with_gtc_stop(self, mock_order, mock_pos, mock_oo, mock_cancel, mock_wait, mock_stop, fake_config):
        mock_oo.return_value = [{"id": "tp-leg", "type": "limit", "side": "sell"}, {"id": "held-stop", "type": "stop_limit", "side": "sell"}]
        assert _ensure_gtc_stop_on_fill("AAPL", {"id": "parent"}, 95.0, fake_config) == 100.25   # the fill ledger's price (069)
        mock_cancel.assert_any_call("tp-leg", fake_config)
        mock_wait.assert_any_call("held-stop", fake_config)
        mock_stop.assert_called_once_with("AAPL", 10.0, 95.0, fake_config)

    @patch("titantrade.entries.place_native_stop_loss")
    @patch("titantrade.entries.cancel_order")
    @patch("titantrade.entries.time.sleep", return_value=None)
    @patch("titantrade.entries.get_order", return_value={"status": "new"})
    def test_unfilled_entry_is_noop(self, mock_order, mock_sleep, mock_cancel, mock_stop, fake_config):
        assert _ensure_gtc_stop_on_fill("AAPL", {"id": "parent"}, 95.0, fake_config) is None
        mock_cancel.assert_not_called()
        mock_stop.assert_not_called()

    @patch("titantrade.entries.place_native_stop_loss", side_effect=RuntimeError("boom"))
    @patch("titantrade.entries._wait_for_order_canceled", return_value="canceled")
    @patch("titantrade.entries.cancel_order")
    @patch("titantrade.entries.get_open_orders", return_value=[{"id": "tp", "side": "sell", "type": "limit"}])
    @patch("titantrade.entries.get_position", return_value={"symbol": "AAPL", "qty": "10"})
    @patch("titantrade.entries.get_order", return_value={"status": "filled"})
    def test_stop_failure_does_not_raise(self, mock_order, mock_pos, mock_oo, mock_cancel, mock_wait, mock_stop, fake_config):
        _ensure_gtc_stop_on_fill("AAPL", {"id": "parent"}, 95.0, fake_config)
        mock_stop.assert_called_once()

    def test_no_parent_is_noop(self, fake_config):
        _ensure_gtc_stop_on_fill("AAPL", None, 95.0, fake_config)
        _ensure_gtc_stop_on_fill("AAPL", {}, 95.0, fake_config)
