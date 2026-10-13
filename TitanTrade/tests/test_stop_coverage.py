"""Decision 060 — bracket legs are DAY orders; stop coverage after a fill.

Production, October 2026: a filled bracket's TP/stop legs expire at the
close. (1) A ticker re-opened after the weekly review took the ADJUST
"keep the entry-time stop" branch, which skipped every check, so FCX sat
without a stop from Fri Oct 2 20:00 to Mon Oct 5 14:15 UTC. (2) The
held-bullish path saw the bracket's TP leg but not its ``held`` stop leg,
cancelled the TP and placed the *thesis* stop instead of the bracket's —
EQIX $969.95 → $1000, tagged Oct 8.
"""

from __future__ import annotations

import json
from dataclasses import replace
from unittest.mock import patch

GEN = "2026-10-04T20:07:00+00:00"   # Sunday review
BEFORE = "2026-10-02T14:15:00+00:00"
AFTER = "2026-10-09T19:30:00+00:00"


def _write(state_dir, name, data):
    (state_dir / name).write_text(json.dumps(data))


def _trade_log(state_dir, *records):
    _write(state_dir, "trade_log.json", {"trades": list(records)})


def _buy(ticker, ts, stop, trigger="bracket_resubmission"):
    return {"ticker": ticker, "action": "BUY", "timestamp": ts,
            "stop_loss_price": stop, "trigger": trigger, "shares": 5}


def _thesis(ticker, stop, review_action="CONTINUE"):
    return {"ticker": ticker, "thesis": "BULLISH", "confidence": 0.7,
            "target_entry_price": stop * 1.05, "stop_loss_price": stop,
            "take_profit_price": stop * 1.2, "selected_for_trading": True,
            "review_action": review_action, "reasoning": "t"}


class TestPositionEntryStop:
    def test_reads_opening_buy_and_skips_pyramid_adds(self, tmp_state_dir):
        from titantrade.trade_state import position_entry_stop
        _trade_log(tmp_state_dir,
                   _buy("EQIX", BEFORE, 969.95),
                   _buy("EQIX", AFTER, 1000.0, trigger="pyramid"))
        assert position_entry_stop("EQIX") == 969.95

    def test_none_when_legacy_record_or_unknown(self, tmp_state_dir):
        from titantrade.trade_state import position_entry_stop
        _trade_log(tmp_state_dir, {"ticker": "EQIX", "action": "BUY", "timestamp": BEFORE})
        assert position_entry_stop("EQIX") is None
        assert position_entry_stop("URI") is None


class TestCoverageStopPrice:
    def test_reopened_position_uses_entry_time_stop(self, tmp_state_dir):
        from titantrade.executor import _coverage_stop_price
        _trade_log(tmp_state_dir, _buy("EQIX", AFTER, 969.95))
        assert _coverage_stop_price("EQIX", _thesis("EQIX", 1000.0), GEN) == 969.95

    def test_position_older_than_review_uses_thesis_stop(self, tmp_state_dir):
        from titantrade.executor import _coverage_stop_price
        _trade_log(tmp_state_dir, _buy("EQIX", BEFORE, 969.95))
        assert _coverage_stop_price("EQIX", _thesis("EQIX", 1000.0), GEN) == 1000.0

    def test_falls_back_to_thesis_without_trade_log_level(self, tmp_state_dir):
        from titantrade.executor import _coverage_stop_price
        _trade_log(tmp_state_dir, {"ticker": "EQIX", "action": "BUY", "timestamp": AFTER})
        assert _coverage_stop_price("EQIX", _thesis("EQIX", 1000.0), GEN) == 1000.0


class TestTpLegRecoveryUsesEntryStop:
    """The EQIX Oct 2 scenario: TP leg visible, stop leg held/invisible."""

    @patch("titantrade.executor.place_native_stop_loss", return_value={"id": "s1"})
    @patch("titantrade.executor.cancel_order")
    @patch("titantrade.executor.get_open_orders")
    def test_places_bracket_stop_not_thesis_stop(self, mock_oo, mock_cancel, mock_place,
                                                 fake_config, tmp_state_dir):
        from titantrade.executor import _ensure_coverage
        _trade_log(tmp_state_dir, _buy("EQIX", AFTER, 969.95))
        tp = {"id": "tp-1", "side": "sell", "type": "limit", "qty": "4", "limit_price": "1143.95"}
        mock_oo.return_value = [{"id": "s1", "side": "sell", "type": "stop_limit", "stop_price": "969.95"}]
        position = {"symbol": "EQIX", "qty": "4", "qty_available": "0"}

        _ensure_coverage("EQIX", _thesis("EQIX", 1000.0), GEN, fake_config,
                         market_open=True, position=position, open_orders=[tp])

        mock_cancel.assert_called_once_with("tp-1", fake_config)
        mock_place.assert_called_once_with("EQIX", 4.0, 969.95, fake_config)

    @patch("titantrade.executor.place_native_stop_loss")
    @patch("titantrade.executor.cancel_order")
    def test_covered_or_fractional_positions_are_left_alone(self, mock_cancel, mock_place,
                                                            fake_config, tmp_state_dir):
        from titantrade.executor import _ensure_coverage
        stop = [{"id": "s1", "side": "sell", "type": "stop_limit", "stop_price": "990"}]
        _ensure_coverage("EQIX", _thesis("EQIX", 1000.0), GEN, fake_config,
                         market_open=True, position={"symbol": "EQIX", "qty": "4"}, open_orders=stop)
        _ensure_coverage("EQIX", _thesis("EQIX", 1000.0), GEN, fake_config,
                         market_open=True, position={"symbol": "EQIX", "qty": "0.4"}, open_orders=[])
        mock_cancel.assert_not_called()
        mock_place.assert_not_called()


class TestAdjustReopenedBranchCoversPosition:
    """End-to-end through execute_trades: the FCX Oct 2 scenario. ADJUST
    levels still don't apply to the re-opened position, but its entry-time
    stop must be put back on the book once the DAY legs are gone."""

    def _state(self, tmp_state_dir):
        _write(tmp_state_dir, "weekly_thesis.json", {
            "generated_at": GEN, "next_review_at": "2026-10-11T20:00:00+00:00",
            "theses": [_thesis("FCX", 75.0, review_action="ADJUST")],
        })
        _write(tmp_state_dir, "sentry_signals.json", {
            "generated_at": AFTER, "signals": [{"ticker": "FCX", "signal": "CONTINUE"}],
            "market_health": {"market_stress": False},
        })
        _write(tmp_state_dir, "data_bundle.json", {"stocks": {}})
        _trade_log(tmp_state_dir, _buy("FCX", AFTER, 69.6))

    @patch("titantrade.executor.place_native_stop_loss", return_value={"id": "s-fcx"})
    @patch("titantrade.executor.cancel_all_orders_for_ticker", return_value=0)
    @patch("titantrade.executor.get_position")
    @patch("titantrade.executor.get_positions")
    @patch("titantrade.executor.get_open_orders", return_value=[])
    @patch("titantrade.executor.get_account", return_value={
        "portfolio_value": "100000", "cash": "20000", "buying_power": "40000",
    })
    @patch("titantrade.executor.resubmit_expired_brackets", return_value=[])
    @patch("titantrade.executor.check_gap_down_protection", return_value=[])
    @patch("titantrade.executor.close_orphaned_positions", return_value=[])
    @patch("titantrade.executor.manage_core_position", return_value=None)
    @patch("titantrade.executor.load_stock_sectors", return_value=None)
    @patch("titantrade.executor.is_market_open", return_value=True)
    def test_entry_time_stop_is_placed(
        self, mock_open, mock_load_sec, mock_core, mock_orphan, mock_gap,
        mock_resub, mock_account, mock_oo, mock_get_positions, mock_get_pos,
        mock_cancel_all, mock_place, fake_config, tmp_state_dir,
    ):
        self._state(tmp_state_dir)
        cfg = replace(fake_config, trading=replace(fake_config.trading, watchlist=["FCX"]))
        position = {"symbol": "FCX", "qty": "109", "current_price": "72.50",
                    "avg_entry_price": "71.79"}
        mock_get_positions.return_value = [position]
        mock_get_pos.return_value = position

        from titantrade.executor import execute_trades
        execute_trades(cfg)

        mock_place.assert_called_once_with("FCX", 109.0, 69.6, cfg)   # bracket level, not $75
        mock_cancel_all.assert_not_called()                            # ADJUST levels not applied


class TestEnsureStopCoverage:
    @patch("titantrade.executor._is_core_ticker", side_effect=lambda t, c: t == "SPY")
    @patch("titantrade.executor.is_market_open", return_value=True)
    @patch("titantrade.executor.place_native_stop_loss")
    @patch("titantrade.executor.get_open_orders")
    @patch("titantrade.executor.get_positions")
    def test_places_only_for_bare_overlay_positions(self, mock_positions, mock_oo, mock_place,
                                                    mock_open, mock_core, fake_config, tmp_state_dir):
        from titantrade.executor import ensure_stop_coverage
        _write(tmp_state_dir, "weekly_thesis.json", {
            "generated_at": GEN,
            "theses": [_thesis("FCX", 69.6), _thesis("CRWD", 258.0)],
        })
        _trade_log(tmp_state_dir)
        mock_positions.return_value = [
            {"symbol": "SPY", "qty": "50"},
            {"symbol": "FCX", "qty": "109"},
            {"symbol": "CRWD", "qty": "64"},
            {"symbol": "GE", "qty": "10"},       # no thesis → orphan path, not ours
        ]
        fcx_orders: list[dict] = []
        book = {"CRWD": [{"id": "s-crwd", "side": "sell", "type": "stop_limit", "stop_price": "258"}],
                "FCX": fcx_orders}
        mock_oo.side_effect = lambda t, c: list(book.get(t, []))
        mock_place.side_effect = lambda t, q, p, c: fcx_orders.append(
            {"id": "s-fcx", "side": "sell", "type": "stop_limit", "stop_price": str(p)}) or {"id": "s-fcx"}

        assert ensure_stop_coverage(fake_config) == 1
        mock_place.assert_called_once_with("FCX", 109.0, 69.6, fake_config)
