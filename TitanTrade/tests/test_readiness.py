"""Decision 071 — go-live readiness: the T-bill leg (off by default) and the heartbeat ping."""
from __future__ import annotations

import json
from dataclasses import replace
from unittest.mock import patch

NOW = "2026-10-29T14:15:00+00:00"


def _cfg(fake_config, **kw):
    return replace(fake_config, trading=replace(fake_config.trading, **kw))


class TestCashLeg:
    def test_off_by_default_and_target_maths(self, fake_config):
        from titantrade.mechanical import cash_target_pct
        assert fake_config.trading.cash_ticker == "" and cash_target_pct(fake_config, 0.5) == 0.0
        cfg = _cfg(fake_config, cash_ticker="SGOV")
        assert cash_target_pct(cfg, 1.0) == 0.0 and cash_target_pct(cfg, 0.5) == 0.475   # (1 − 0.5) × 95 %

    def test_it_is_a_core_leg_for_the_plan_and_the_gates(self, fake_config):
        from titantrade.core_allocation import _is_core_ticker, core_tickers
        from titantrade.risk_manager import _core_legs
        cfg = _cfg(fake_config, cash_ticker="SGOV")
        assert _is_core_ticker("SGOV", cfg) and core_tickers(cfg) == ("SPY", "SPMO", "SGOV") == _core_legs(cfg)
        assert not _is_core_ticker("SGOV", fake_config) and _core_legs(fake_config) == ("SPY", "SPMO")

    def test_plan_carries_the_leg_only_when_configured(self, fake_config, tmp_state_dir):
        from titantrade.mechanical import build_plan
        (tmp_state_dir / "trade_log.json").write_text(json.dumps({"trades": []}))
        bundle = {"stocks": {}, "market_context": {"breadth": {"spy_above_sma": False, "pct": 0.3}}}
        plan = build_plan(_cfg(fake_config, watchlist=[], cash_ticker="SGOV"), bundle, [], set(), started_at=NOW)
        assert plan["insurance"]["risk_off"] and plan["cash_leg"] == {"ticker": "SGOV", "target_pct": 0.475}
        assert build_plan(_cfg(fake_config, watchlist=[]), bundle, [], set(), started_at=NOW)["cash_leg"] is None

    @patch("titantrade.executor.record_stop_out_cooldowns", return_value=0)
    @patch("titantrade.executor.check_gap_down_protection", return_value=[])
    @patch("titantrade.executor.close_orphaned_positions", return_value=[])
    @patch("titantrade.executor.manage_core_position", return_value=None)
    @patch("titantrade.executor.load_stock_sectors", return_value=None)
    @patch("titantrade.executor.get_open_orders", return_value=[])
    @patch("titantrade.executor.get_positions")
    @patch("titantrade.executor.get_account", return_value={"portfolio_value": "100000", "cash": "40000", "buying_power": "80000"})
    @patch("titantrade.executor.is_market_open", return_value=True)
    def test_executor_buys_the_leg_last_and_sells_it_first(self, mock_open, mock_account, mock_positions, mock_oo, mock_sec, mock_core,
                                                           mock_orphan, mock_gap, mock_cooldown, fake_config, tmp_state_dir):
        from titantrade.executor import execute_trades
        cfg = _cfg(fake_config, watchlist=["AAA"], momentum_weight=0.6, cash_ticker="SGOV")
        (tmp_state_dir / "data_bundle.json").write_text(json.dumps({"generated_at": NOW, "stocks": {}}))
        # de-risked (scale 0.5), no SGOV yet → SPY, SPMO, then SGOV buys the idle 47.5 %
        (tmp_state_dir / "plan.json").write_text(json.dumps({"generated_at": NOW, "exposure_scale": 0.5, "items": [], "watch": [{"ticker": "AAA", "reason": "no signal"}]}))
        mock_positions.return_value = [{"symbol": "SPY", "qty": "70", "market_value": "60000"}]
        execute_trades(cfg)
        assert [(c.kwargs["ticker"], c.kwargs["target_pct"]) for c in mock_core.call_args_list] == [("SPY", 0.19), ("SPMO", 0.285), ("SGOV", 0.475)]
        # back to full exposure with SGOV held → SGOV sells first so its cash funds the re-risking
        mock_core.reset_mock()
        (tmp_state_dir / "plan.json").write_text(json.dumps({"generated_at": NOW, "exposure_scale": 1.0, "items": [], "watch": [{"ticker": "AAA", "reason": "no signal"}]}))
        mock_positions.return_value = [{"symbol": "SPY", "qty": "20", "market_value": "19000"}, {"symbol": "SGOV", "qty": "470", "market_value": "47500"}]
        execute_trades(cfg)
        assert [c.kwargs["ticker"] for c in mock_core.call_args_list] == ["SGOV", "SPY", "SPMO"] and mock_core.call_args_list[0].kwargs["target_pct"] == 0.0
        # off (default): never a third leg
        mock_core.reset_mock()
        execute_trades(_cfg(fake_config, watchlist=["AAA"], momentum_weight=0.6))
        assert [c.kwargs["ticker"] for c in mock_core.call_args_list] == ["SPY", "SPMO"]


class TestHeartbeat:
    def test_pings_after_a_successful_summary_only_when_configured(self, monkeypatch):
        from titantrade.scheduler import _run_daily_summary
        monkeypatch.setenv("HEALTHCHECK_PING_URL", "https://hc-ping.com/abc")
        with patch("titantrade.benchmark.compute_benchmark"), patch("titantrade.fill_ledger.update_fill_ledger", return_value=0), \
             patch("titantrade.notifier.send_daily_summary", return_value="daily summary sent"), patch("titantrade.config.load_config", return_value=object()), \
             patch("httpx.get") as get:
            assert _run_daily_summary() == "daily summary sent"
        get.assert_called_once_with("https://hc-ping.com/abc", timeout=10.0)
        monkeypatch.delenv("HEALTHCHECK_PING_URL")
        with patch("titantrade.benchmark.compute_benchmark"), patch("titantrade.fill_ledger.update_fill_ledger", return_value=0), \
             patch("titantrade.notifier.send_daily_summary", return_value="ok"), patch("titantrade.config.load_config", return_value=object()), \
             patch("httpx.get") as get:
            _run_daily_summary()
        get.assert_not_called()

    def test_a_failed_ping_never_fails_the_summary(self, monkeypatch):
        from titantrade.scheduler import _ping_heartbeat
        monkeypatch.setenv("HEALTHCHECK_PING_URL", "https://hc-ping.com/abc")
        with patch("httpx.get", side_effect=RuntimeError("down")):
            _ping_heartbeat()   # logs, does not raise
