"""The executor: stop coverage, held-position exits, and an end-to-end run.
All broker calls mocked."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from titantrade.executor import _ensure_coverage, _manage_held, ensure_stop_coverage, execute_trades

NOW = "2026-10-13T14:15:00+00:00"


def _write(state_dir, name, data):
    (state_dir / name).write_text(json.dumps(data))


def _log(state_dir, ticker, opened_at, stop=88.0):
    _write(state_dir, "trade_log.json", {"trades": [{"ticker": ticker, "action": "BUY", "timestamp": opened_at, "stop_price": stop, "trigger": "entry"}]})


class TestStopCoverage:
    @patch("titantrade.executor.place_native_stop_loss", return_value={"id": "s1"})
    @patch("titantrade.executor.cancel_order")
    @patch("titantrade.executor.get_open_orders")
    def test_tp_leg_without_stop_gets_the_plan_stop(self, mock_oo, mock_cancel, mock_place, fake_config):
        """The EQIX Oct 2 scenario: the bracket's TP leg is visible, its stop leg is held."""
        tp = {"id": "tp-1", "side": "sell", "type": "limit", "qty": "4", "limit_price": "1143.95"}
        mock_oo.return_value = [{"id": "s1", "side": "sell", "type": "stop_limit", "stop_price": "969.95"}]
        _ensure_coverage("EQIX", 969.95, fake_config, market_open=True, position={"symbol": "EQIX", "qty": "4", "qty_available": "0"}, open_orders=[tp])
        mock_cancel.assert_called_once_with("tp-1", fake_config)
        mock_place.assert_called_once_with("EQIX", 4.0, 969.95, fake_config)

    @patch("titantrade.executor.place_native_stop_loss")
    @patch("titantrade.executor.cancel_order")
    def test_covered_fractional_or_unknown_level_is_left_alone(self, mock_cancel, mock_place, fake_config):
        stop = [{"id": "s1", "side": "sell", "type": "stop_limit", "stop_price": "990"}]
        _ensure_coverage("EQIX", 1000.0, fake_config, market_open=True, position={"symbol": "EQIX", "qty": "4"}, open_orders=stop)
        _ensure_coverage("EQIX", 1000.0, fake_config, market_open=True, position={"symbol": "EQIX", "qty": "0.4"}, open_orders=[])
        _ensure_coverage("EQIX", None, fake_config, market_open=True, position={"symbol": "EQIX", "qty": "4"}, open_orders=[])
        mock_cancel.assert_not_called()
        mock_place.assert_not_called()

    @patch("titantrade.executor.place_native_stop_loss")
    def test_market_closed_defers(self, mock_place, fake_config):
        _ensure_coverage("EQIX", 1000.0, fake_config, market_open=False, position={"symbol": "EQIX", "qty": "4"}, open_orders=[])
        mock_place.assert_not_called()

    @patch("titantrade.executor.is_market_open", return_value=True)
    @patch("titantrade.executor.place_native_stop_loss")
    @patch("titantrade.executor.get_open_orders")
    @patch("titantrade.executor.get_positions")
    def test_gapcheck_companion_covers_only_bare_plan_positions(self, mock_positions, mock_oo, mock_place, mock_open, fake_config, tmp_state_dir):
        _write(tmp_state_dir, "plan.json", {"items": [{"ticker": "FCX", "action": "HOLD", "stop_price": 69.6}, {"ticker": "CRWD", "action": "HOLD", "stop_price": 258.0}]})
        mock_positions.return_value = [{"symbol": "SPY", "qty": "50"}, {"symbol": "FCX", "qty": "109"}, {"symbol": "CRWD", "qty": "64"}, {"symbol": "GE", "qty": "10"}]
        fcx: list[dict] = []
        book = {"CRWD": [{"id": "s-crwd", "side": "sell", "type": "stop_limit", "stop_price": "258"}], "FCX": fcx}
        mock_oo.side_effect = lambda t, c: list(book.get(t, []))
        mock_place.side_effect = lambda t, q, p, c: fcx.append({"id": "s-fcx", "side": "sell", "type": "stop_limit", "stop_price": str(p)}) or {"id": "s-fcx"}
        assert ensure_stop_coverage(fake_config) == 1
        mock_place.assert_called_once_with("FCX", 109.0, 69.6, fake_config)


class TestHeldExits:
    def _run(self, fake_config, position, open_orders):
        item = {"ticker": "BBB", "action": "HOLD", "stop_price": 88.0}
        with patch("titantrade.executor.get_position", return_value=position), \
             patch("titantrade.executor.get_open_orders", return_value=open_orders), \
             patch("titantrade.executor.close_position_settled", return_value={"ticker": "BBB", "action": "SELL", "trigger": "x"}) as close, \
             patch("titantrade.executor.place_native_stop_loss") as place:
            trades = _manage_held(item, fake_config, market_open=True)
        return trades, close, place

    def test_target_closes(self, fake_config, tmp_state_dir):
        _log(tmp_state_dir, "BBB", (datetime.now(timezone.utc) - timedelta(days=10)).isoformat())
        stop = [{"id": "s1", "side": "sell", "type": "stop_limit", "stop_price": "88"}]
        trades, close, _ = self._run(fake_config, {"symbol": "BBB", "qty": "10", "unrealized_plpc": "0.21"}, stop)
        assert trades and close.call_args.kwargs["trigger"] == "target"

    def test_holding_limit_closes(self, fake_config, tmp_state_dir):
        _log(tmp_state_dir, "BBB", (datetime.now(timezone.utc) - timedelta(days=100)).isoformat())
        stop = [{"id": "s1", "side": "sell", "type": "stop_limit", "stop_price": "88"}]
        trades, close, _ = self._run(fake_config, {"symbol": "BBB", "qty": "10", "unrealized_plpc": "0.01"}, stop)
        assert trades and close.call_args.kwargs["trigger"] == "holding_limit"

    def test_otherwise_only_coverage(self, fake_config, tmp_state_dir):
        _log(tmp_state_dir, "BBB", (datetime.now(timezone.utc) - timedelta(days=10)).isoformat())
        trades, close, place = self._run(fake_config, {"symbol": "BBB", "qty": "10", "unrealized_plpc": "0.02"}, [])
        assert trades == [] and not close.called
        place.assert_called_once_with("BBB", 10.0, 88.0, fake_config)


class TestExecuteTradesEndToEnd:
    @patch("titantrade.entries.get_latest_price", return_value=88.0)
    @patch("titantrade.entries.place_bracket_order", return_value={"id": "b1"})
    @patch("titantrade.entries.get_open_orders", return_value=[])
    @patch("titantrade.executor.record_stop_out_cooldowns", return_value=0)
    @patch("titantrade.executor.resubmit_expired_brackets", return_value=[])
    @patch("titantrade.executor.check_gap_down_protection", return_value=[])
    @patch("titantrade.executor.close_orphaned_positions", return_value=[])
    @patch("titantrade.executor.manage_core_position", return_value=None)
    @patch("titantrade.executor.load_stock_sectors", return_value=None)
    @patch("titantrade.executor.get_open_orders", return_value=[])
    @patch("titantrade.executor.get_positions")
    @patch("titantrade.executor.get_account", return_value={"portfolio_value": "100000", "cash": "40000", "buying_power": "80000"})
    @patch("titantrade.executor.is_market_open", return_value=True)
    def test_new_item_becomes_a_slot_bracket_and_core_gets_the_residual(
        self, mock_open, mock_account, mock_positions, mock_oo, mock_sec, mock_core, mock_orphan, mock_gap,
        mock_resub, mock_cooldown, mock_entry_oo, mock_bracket, mock_price, fake_config, tmp_state_dir, monkeypatch,
    ):
        monkeypatch.setattr("titantrade.risk_manager.get_stock_sector", lambda t: "ETF" if t == "SPY" else "Technology")
        cfg = replace(fake_config, trading=replace(fake_config.trading, watchlist=["AAA"]))
        _write(tmp_state_dir, "plan.json", {"generated_at": NOW, "insurance": {"exposure_scale": 1.0}, "watch": [],
                                            "items": [{"ticker": "AAA", "action": "NEW", "entry_price": 88.0, "stop_price": 77.44, "target_price": 105.6, "dip_pct": 0.12, "reason": "dip"}]})
        _write(tmp_state_dir, "data_bundle.json", {"generated_at": NOW, "stocks": {"AAA": {"atr_14": 2.0}}})
        mock_positions.return_value = [{"symbol": "SPY", "qty": "70", "market_value": "60000"}]

        trades = execute_trades(cfg)

        mock_orphan.assert_called_once()
        assert mock_core.call_args.kwargs["target_pct"] == 0.70                  # 0.95 − one planned 25% slot
        assert mock_bracket.call_args.kwargs["qty"] == 283.0                     # 25% of $100k at $88.26
        assert trades and trades[0]["ticker"] == "AAA" and trades[0]["action"] == "BUY"
        snap = json.loads((tmp_state_dir / "portfolio.json").read_text())
        assert snap["portfolio_value"] == 100000.0 and snap["positions"][0]["symbol"] == "SPY"

    @patch("titantrade.executor.get_account")
    @patch("titantrade.executor.check_gap_down_protection", return_value=[])
    @patch("titantrade.executor.close_orphaned_positions", return_value=[])
    @patch("titantrade.executor.load_stock_sectors", return_value=None)
    @patch("titantrade.executor.is_market_open", return_value=True)
    def test_no_plan_skips_execution(self, mock_open, mock_sec, mock_orphan, mock_gap, mock_account, fake_config, tmp_state_dir):
        assert execute_trades(fake_config) == []
        mock_account.assert_not_called()
