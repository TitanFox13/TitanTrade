"""Decision 061 — the mechanical strategy: signals, thesis generation, core
target, slot sizing, held-position exits, scheduler wiring, backtester,
curator and API. Zero network: every broker/LLM call is mocked."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from titantrade.signals import (
    breadth, dip_state, evaluate_dip, insurance_state, rank_dips, sma,
    trading_days_between,
)

STARTED = "2026-10-14T12:00:00+00:00"
BEFORE = "2026-10-01T14:15:00+00:00"
AFTER = "2026-10-15T14:15:00+00:00"


def _mech_cfg(fake_config, **kw):
    t = dict(strategy="mechanical", watchlist=["AAA", "BBB", "CCC", "DDD"], max_slots=2)
    t.update(kw)
    return replace(fake_config, trading=replace(fake_config.trading, **t))


def _write(state_dir, name, data):
    (state_dir / name).write_text(json.dumps(data))


def _bundle(spy_above=True, pct=0.7, **inputs):
    stocks = {t: {"signal_inputs": v} for t, v in inputs.items()}
    return {"generated_at": AFTER, "market_context": {"market_regime": "bull", "breadth": {"spy_above_sma": spy_above, "pct": pct}}, "stocks": stocks}


def _inp(close, high, trend):
    return {"close": close, "high_lookback": high, "sma_trend": trend, "lookback_days": 60, "trend_sma_days": 200}


class TestSignals:
    def test_dip_in_uptrend_signal(self):
        s = evaluate_dip(88.0, 100.0, 85.0, dip_pct=0.10)
        assert s["signal"] is True and s["dip_pct"] == 0.12 and s["above_trend"] is True

    def test_dip_below_trend_is_not_a_signal(self):
        assert evaluate_dip(88.0, 100.0, 90.0, dip_pct=0.10)["signal"] is False

    def test_shallow_dip_is_not_a_signal(self):
        assert evaluate_dip(95.0, 100.0, 85.0, dip_pct=0.10)["signal"] is False

    def test_missing_inputs_fail_closed(self):
        s = evaluate_dip(None, 100.0, 85.0, dip_pct=0.10)
        assert s["signal"] is False and s["dip_pct"] is None

    def test_dip_state_uses_window_high_and_sma(self):
        closes = [100.0] * 200 + [120.0] + [105.0]
        s = dip_state(closes, dip_pct=0.10, lookback=60, trend_sma=200)
        assert s["high"] == 120.0 and s["signal"] is True
        assert sma(closes, 200) is not None

    def test_breadth_and_insurance(self):
        assert breadth([True, False, None, True]) == 2 / 3
        assert breadth([None]) is None
        on = insurance_state(True, 0.2, breadth_threshold=0.5, scale=0.5)
        assert on["risk_off"] is False and on["exposure_scale"] == 1.0
        off = insurance_state(False, 0.4, breadth_threshold=0.5, scale=0.5)
        assert off["risk_off"] is True and off["exposure_scale"] == 0.5
        # one signal alone is not enough, and unknowns fail open
        assert insurance_state(False, 0.6, breadth_threshold=0.5, scale=0.5)["risk_off"] is False
        assert insurance_state(None, 0.1, breadth_threshold=0.5, scale=0.5)["risk_off"] is False

    def test_rank_dips_deepest_first(self):
        states = {"A": {"signal": True, "dip_pct": 0.11}, "B": {"signal": True, "dip_pct": 0.15}, "C": {"signal": False, "dip_pct": 0.2}}
        assert rank_dips(states) == ["B", "A"]

    def test_trading_days_between_counts_weekdays(self):
        end = datetime(2026, 10, 13, tzinfo=timezone.utc)  # Tuesday
        assert trading_days_between("2026-10-06T14:15:00+00:00", end) == 5
        assert trading_days_between(None, end) == 0


class TestBuildTheses:
    def _trade_log(self, state_dir):
        _write(state_dir, "trade_log.json", {"trades": [
            {"ticker": "EEE", "action": "BUY", "timestamp": BEFORE, "stop_loss_price": 50.0, "take_profit_price": 70.0, "trigger": "weekly_thesis"},
            {"ticker": "BBB", "action": "BUY", "timestamp": AFTER, "stop_loss_price": 90.0, "take_profit_price": 110.0, "trigger": "weekly_thesis"},
        ]})

    def test_held_legacy_and_ranked_candidates(self, fake_config, tmp_state_dir):
        from titantrade.mechanical import build_theses
        self._trade_log(tmp_state_dir)
        cfg = _mech_cfg(fake_config)
        bundle = _bundle(AAA=_inp(88, 100, 80), BBB=_inp(100, 100, 80), CCC=_inp(85, 100, 90), DDD=_inp(89, 100, 80))
        positions = [{"symbol": "SPY", "qty": "50", "market_value": "38000"},
                     {"symbol": "BBB", "qty": "10", "avg_entry_price": "100", "market_value": "1000"},
                     {"symbol": "EEE", "qty": "5", "avg_entry_price": "60", "market_value": "300"}]
        theses, summary = build_theses(cfg, bundle, positions, set(), started_at=STARTED)
        by = {t["ticker"]: t for t in theses}
        assert by["BBB"]["review_action"] == "CONTINUE" and by["BBB"]["stop_loss_price"] == 90.0 and by["BBB"]["take_profit_price"] == 110.0
        assert "EEE" not in by and summary["legacy_to_close"] == ["EEE"]
        assert summary["free_slots"] == 1  # max_slots 2 − 1 held mechanical
        assert by["AAA"]["review_action"] == "NEW" and by["AAA"]["selected_for_trading"] is True
        assert by["AAA"]["stop_loss_price"] == round(88 * 0.88, 2) and by["AAA"]["take_profit_price"] == round(88 * 1.10, 2)
        assert by["DDD"]["thesis"] == "NEUTRAL" and "no free slot" in by["DDD"]["reasoning"]
        assert by["CCC"]["thesis"] == "NEUTRAL"
        assert [c["ticker"] for c in summary["candidates"]] == ["AAA", "DDD"]

    def test_risk_off_blocks_new_entries_but_keeps_held(self, fake_config, tmp_state_dir):
        from titantrade.mechanical import build_theses
        self._trade_log(tmp_state_dir)
        cfg = _mech_cfg(fake_config)
        bundle = _bundle(spy_above=False, pct=0.3, AAA=_inp(88, 100, 80), BBB=_inp(100, 100, 80), CCC=_inp(100, 100, 80), DDD=_inp(100, 100, 80))
        positions = [{"symbol": "BBB", "qty": "10", "avg_entry_price": "100", "market_value": "1000"}]
        theses, summary = build_theses(cfg, bundle, positions, set(), started_at=STARTED)
        by = {t["ticker"]: t for t in theses}
        assert summary["insurance"]["risk_off"] is True and summary["new_signals"] == 0
        assert by["AAA"]["thesis"] == "NEUTRAL" and "risk-off" in by["AAA"]["reasoning"]
        assert by["BBB"]["review_action"] == "CONTINUE"

    def test_pending_bracket_occupies_a_slot_and_keeps_its_thesis(self, fake_config, tmp_state_dir):
        from titantrade.mechanical import build_theses
        self._trade_log(tmp_state_dir)
        cfg = _mech_cfg(fake_config, max_slots=1)
        bundle = _bundle(AAA=_inp(88, 100, 80), BBB=_inp(100, 100, 80), CCC=_inp(100, 100, 80), DDD=_inp(89, 100, 80))
        theses, summary = build_theses(cfg, bundle, [], {"DDD"}, started_at=STARTED)
        by = {t["ticker"]: t for t in theses}
        assert summary["free_slots"] == 0
        assert by["DDD"]["review_action"] == "NEW" and by["DDD"]["selected_for_trading"] is True
        assert by["AAA"]["thesis"] == "NEUTRAL"

    def test_stale_signal_inputs_are_flagged(self, fake_config, tmp_state_dir, caplog):
        from titantrade.mechanical import build_theses
        self._trade_log(tmp_state_dir)
        cfg = _mech_cfg(fake_config, dip_lookback_days=90, trend_sma_days=150)
        bundle = _bundle(AAA=_inp(88, 100, 80), BBB=_inp(100, 100, 80), CCC=_inp(100, 100, 80), DDD=_inp(100, 100, 80))  # inputs say 60/200
        with caplog.at_level("WARNING"):
            build_theses(cfg, bundle, [], set(), started_at=STARTED)
        assert "run `titantrade fetch`" in caplog.text

    def test_refresh_writes_the_three_state_files(self, fake_config, tmp_state_dir):
        from titantrade.mechanical import refresh_mechanical_signals
        self._trade_log(tmp_state_dir)
        cfg = _mech_cfg(fake_config)
        _write(tmp_state_dir, "data_bundle.json", _bundle(AAA=_inp(88, 100, 80), BBB=_inp(100, 100, 80), CCC=_inp(100, 100, 80), DDD=_inp(100, 100, 80)))
        with patch("titantrade.mechanical.get_positions", return_value=[]), \
             patch("titantrade.mechanical.get_open_orders", return_value=[]):
            summary = refresh_mechanical_signals(cfg)
        assert summary["new_signals"] == 1
        thesis = json.loads((tmp_state_dir / "weekly_thesis.json").read_text())
        sentry = json.loads((tmp_state_dir / "sentry_signals.json").read_text())
        strategy = json.loads((tmp_state_dir / "strategy.json").read_text())
        assert thesis["strategy"] == "mechanical" and any(t["ticker"] == "AAA" and t["selected_for_trading"] for t in thesis["theses"])
        assert sentry["market_health"]["market_stress"] is False and all(s["signal"] == "CONTINUE" for s in sentry["signals"])
        assert strategy["started_at"] and (tmp_state_dir / "signals.json").exists()


class TestCoreTarget:
    def test_residual_after_overlay_and_planned_slots(self, fake_config):
        from titantrade.mechanical import core_target_pct
        cfg = _mech_cfg(fake_config)
        positions = [{"symbol": "SPY", "market_value": "60000"}, {"symbol": "BBB", "market_value": "20000"}]
        assert core_target_pct(cfg, 100_000, positions, planned_new_slots=1, exposure_scale=1.0) == 0.55
        assert core_target_pct(cfg, 100_000, positions, planned_new_slots=1, exposure_scale=0.5) == 0.075
        assert core_target_pct(cfg, 100_000, positions, planned_new_slots=3, exposure_scale=1.0) == 0.15
        assert core_target_pct(cfg, 100_000, positions, planned_new_slots=4, exposure_scale=1.0) == 0.0


class TestSlotSizing:
    def test_mechanical_sizing_is_a_flat_slot(self, fake_config, tmp_state_dir):
        from titantrade.risk_manager import pre_trade_check
        cfg = _mech_cfg(fake_config, slot_pct=0.20)
        thesis = {"ticker": "AAA", "confidence": 0.80, "target_entry_price": 100.0, "stop_loss_price": 88.0, "take_profit_price": 110.0, "sector": "Technology"}
        with patch("titantrade.risk_manager.get_stock_sector", return_value="Technology"):
            check = pre_trade_check("AAA", thesis, 100_000, 50_000, [], stock_atr=1.0, earnings_blocked=False, cfg=cfg)
        assert check["allowed"] and check["shares"] == 200.0


class TestHeldMechanical:
    def _log(self, state_dir, opened_at):
        _write(state_dir, "trade_log.json", {"trades": [{"ticker": "BBB", "action": "BUY", "timestamp": opened_at, "stop_loss_price": 88.0, "trigger": "weekly_thesis"}]})

    def _run(self, fake_config, position, open_orders):
        from titantrade.executor import _manage_held_mechanical
        cfg = _mech_cfg(fake_config, max_hold_days=40)
        thesis = {"ticker": "BBB", "stop_loss_price": 88.0}
        with patch("titantrade.executor.get_position", return_value=position), \
             patch("titantrade.executor.get_open_orders", return_value=open_orders), \
             patch("titantrade.executor.cancel_order") as cancel, \
             patch("titantrade.executor._wait_for_order_canceled", return_value="canceled"), \
             patch("titantrade.executor.close_position_at_market", return_value={"id": "c"}) as close, \
             patch("titantrade.executor.place_native_stop_loss") as place:
            trades = _manage_held_mechanical("BBB", thesis, cfg, market_open=True, thesis_generated_at=AFTER)
        return trades, cancel, close, place

    def test_target_hit_closes_after_settling_the_stop(self, fake_config, tmp_state_dir):
        self._log(tmp_state_dir, (datetime.now(timezone.utc) - timedelta(days=10)).isoformat())
        stop = {"id": "s1", "side": "sell", "type": "stop_limit", "stop_price": "88"}
        trades, cancel, close, place = self._run(fake_config, {"symbol": "BBB", "qty": "10", "unrealized_plpc": "0.12", "current_price": "112"}, [stop])
        assert trades and trades[0]["trigger"] == "mechanical_tp"
        cancel.assert_called_once()
        close.assert_called_once()
        place.assert_not_called()

    def test_holding_limit_closes(self, fake_config, tmp_state_dir):
        self._log(tmp_state_dir, (datetime.now(timezone.utc) - timedelta(days=70)).isoformat())
        stop = {"id": "s1", "side": "sell", "type": "stop_limit", "stop_price": "88"}
        trades, _, close, _ = self._run(fake_config, {"symbol": "BBB", "qty": "10", "unrealized_plpc": "0.01", "current_price": "101"}, [stop])
        assert trades and trades[0]["trigger"] == "mechanical_time"
        close.assert_called_once()

    def test_otherwise_only_coverage_runs(self, fake_config, tmp_state_dir):
        self._log(tmp_state_dir, (datetime.now(timezone.utc) - timedelta(days=10)).isoformat())
        trades, cancel, close, place = self._run(fake_config, {"symbol": "BBB", "qty": "10", "unrealized_plpc": "0.02", "current_price": "102"}, [])
        assert trades == [] and close.call_count == 0
        place.assert_called_once_with("BBB", 10.0, 88.0, _mech_cfg(fake_config, max_hold_days=40))


class TestExecuteTradesMechanical:
    """End-to-end through execute_trades: a NEW signal becomes a slot-sized
    bracket, the core gets the residual target, held mechanical names are
    managed by the mechanical path."""

    @patch("titantrade.daily_sentry._fetch_current_price", return_value=88.0)
    @patch("titantrade.entries.place_bracket_order", return_value={"id": "b1"})
    @patch("titantrade.entries.get_open_orders", return_value=[])
    @patch("titantrade.executor.get_position")
    @patch("titantrade.executor.get_positions")
    @patch("titantrade.executor.get_open_orders", return_value=[])
    @patch("titantrade.executor.get_account", return_value={"portfolio_value": "100000", "cash": "40000", "buying_power": "80000"})
    @patch("titantrade.executor.resubmit_expired_brackets", return_value=[])
    @patch("titantrade.executor.record_stop_out_cooldowns", return_value=0)
    @patch("titantrade.executor.check_gap_down_protection", return_value=[])
    @patch("titantrade.executor.close_orphaned_positions", return_value=[])
    @patch("titantrade.executor.manage_core_position", return_value=None)
    @patch("titantrade.executor.load_stock_sectors", return_value=None)
    @patch("titantrade.executor.is_market_open", return_value=True)
    def test_signal_becomes_slot_bracket(
        self, mock_open, mock_sec, mock_core, mock_orphan, mock_gap, mock_cooldown, mock_resub,
        mock_account, mock_oo, mock_positions, mock_position, mock_entry_oo, mock_bracket, mock_price,
        fake_config, tmp_state_dir,
    ):
        cfg = _mech_cfg(fake_config, watchlist=["AAA"], slot_pct=0.20)
        _write(tmp_state_dir, "weekly_thesis.json", {"generated_at": AFTER, "strategy": "mechanical", "theses": [
            {"ticker": "AAA", "thesis": "BULLISH", "confidence": 0.80, "target_entry_price": 88.0, "stop_loss_price": 77.44,
             "take_profit_price": 96.8, "selected_for_trading": True, "review_action": "NEW", "reasoning": "dip", "sector": "Technology"},
        ]})
        _write(tmp_state_dir, "sentry_signals.json", {"generated_at": AFTER, "market_health": {"market_stress": False, "exposure_scale": 1.0}, "signals": [{"ticker": "AAA", "signal": "CONTINUE"}]})
        _write(tmp_state_dir, "data_bundle.json", {"generated_at": AFTER, "stocks": {"AAA": {"atr_14": 2.0, "technical_indicators": {"price_vs_sma": {"above_sma_50": False, "above_sma_200": True, "pct_from_sma_50": -5.0}}}}})
        mock_positions.return_value = [{"symbol": "SPY", "qty": "70", "market_value": "60000"}]
        mock_position.return_value = None

        from titantrade.executor import execute_trades
        with patch("titantrade.risk_manager.get_stock_sector", side_effect=lambda t: "ETF" if t == "SPY" else "Technology"):
            trades = execute_trades(cfg)

        mock_core.assert_called_once()
        assert mock_core.call_args.kwargs["target_pct"] == 0.75   # 0.95 − one planned 20% slot
        assert mock_bracket.called
        qty_total = sum(c.kwargs["qty"] for c in mock_bracket.call_args_list)
        assert qty_total == 227.0                                  # 20% of $100k at the $88 thesis price, two tranches
        assert trades and trades[0]["ticker"] == "AAA" and trades[0]["action"] == "BUY"


class TestSchedulerWiring:
    def test_execute_refreshes_signals_under_mechanical(self, fake_config):
        from titantrade import scheduler
        cfg = _mech_cfg(fake_config)
        with patch("titantrade.config.load_config", return_value=cfg), \
             patch("titantrade.mechanical.refresh_mechanical_signals", return_value={"new_signals": 0, "risk_off": False}) as refresh, \
             patch("titantrade.executor.execute_trades", return_value=[{"ticker": "AAA"}]) as execute:
            out = scheduler._run_execute()
        refresh.assert_called_once()
        execute.assert_called_once()
        assert out == "1 trades executed"

    def test_full_under_mechanical_skips_the_llms(self, fake_config):
        from titantrade import scheduler
        cfg = _mech_cfg(fake_config)
        with patch("titantrade.config.load_config", return_value=cfg), \
             patch("titantrade.data_fetcher.main") as fetch, \
             patch("titantrade.mechanical.refresh_mechanical_signals", return_value={}) as refresh, \
             patch("titantrade.executor.execute_trades", return_value=[]), \
             patch("titantrade.weekly_analyst.run_weekly_analysis") as analyst:
            scheduler._run_full()
        fetch.assert_called_once()
        refresh.assert_called_once()
        analyst.assert_not_called()


def _bars(closes, start=datetime(2024, 1, 1)):
    out = []
    d = start
    for c in closes:
        while d.weekday() >= 5:
            d += timedelta(days=1)
        out.append({"date": d.strftime("%Y-%m-%d"), "open": c, "high": c, "low": c, "close": c, "volume": 1000})
        d += timedelta(days=1)
    return out


class TestBacktestMechanical:
    def test_dip_in_uptrend_is_bought_and_exits_at_target(self):
        from titantrade.backtest.mechanical import run_mechanical_backtest
        n = 400
        spy = [100 + 0.05 * i for i in range(n)]
        aaa = [100 + 0.3 * i for i in range(300)]                    # steep trend: SMA200 ≈ 160 at a 190 peak
        peak = aaa[-1]
        aaa += [peak * (1 - 0.03 * k) for k in range(1, 5)]          # −12% over 4 days, still above the SMA200
        low = aaa[-1]
        aaa += [low * (1 + 0.025 * k) for k in range(1, 9)]          # +20% recovery → target hit
        aaa += [aaa[-1]] * (n - len(aaa))
        res = run_mechanical_backtest({"AAA": _bars(aaa)}, _bars(spy), None, {"max_slots": 1})
        assert res["metrics"]["trades"] == 1
        t = res["trades"][0]
        assert t["exit"] == "tp" and t["return"] >= 0.10
        assert res["metrics"]["total_return"] > res["spy"]["total_return"]

    def test_insurance_scales_exposure_in_a_broad_decline(self):
        from titantrade.backtest.mechanical import run_mechanical_backtest
        spy = [100 + 0.05 * i for i in range(300)] + [115 - 0.2 * k for k in range(1, 101)]
        sectors = {f"X{i}": _bars(spy) for i in range(4)}
        res = run_mechanical_backtest({"AAA": _bars(spy)}, _bars(spy), sectors, {})
        assert res["risk_off_days"] > 0
        assert res["avg_exposure"] < 0.95
        assert res["metrics"]["max_drawdown"] > res["spy"]["max_drawdown"]   # shallower fall than SPY

    def test_walk_forward_reports_both_halves(self):
        from titantrade.backtest.mechanical import walk_forward
        spy = [100 + 0.05 * i for i in range(500)]
        rows = walk_forward({"AAA": _bars(spy)}, _bars(spy), None, [{"dip_pct": 0.1}, {"dip_pct": 0.2}], split="2025-01-01")
        assert len(rows) == 2 and {"in_sample", "out_of_sample"} <= rows[0].keys()


class TestCurator:
    def test_universe_review_writes_proposal_without_touching_orders(self, fake_config, tmp_state_dir):
        from titantrade.curator import build_universe_prompt, run_universe_review
        cfg = _mech_cfg(fake_config)
        _write(tmp_state_dir, "data_bundle.json", {"generated_at": AFTER, "market_context": {"market_regime": "bull"}, "stocks": {"AAA": {"news": [{"title": "x"}]}}})
        _write(tmp_state_dir, "trade_log.json", {"trades": [{"ticker": "AAA", "action": "BUY", "timestamp": AFTER}]})
        system, user = build_universe_prompt(cfg, json.loads((tmp_state_dir / "data_bundle.json").read_text()), [])
        assert "AAA" in user and "JSON" in system
        reply = 'Sure: {"remove": [{"ticker": "CCC", "reason": "weak"}], "add": [{"ticker": "MSFT", "sector": "Technology", "reason": "durable"}], "notes": "ok"}'
        with patch("titantrade.weekly_analyst._call_claude", return_value=reply), \
             patch("titantrade.notifier.send_discord") as discord:
            doc = run_universe_review(cfg)
        assert doc["proposal"]["add"][0]["ticker"] == "MSFT"
        assert json.loads((tmp_state_dir / "universe_proposal.json").read_text())["status"].startswith("advisory")
        discord.assert_called_once()


class TestApi:
    def test_signals_endpoint(self):
        from fastapi.testclient import TestClient
        from titantrade.api import app
        client = TestClient(app)
        with patch("titantrade.api._read_state", return_value={}):
            assert client.get("/api/signals").status_code == 404
        with patch("titantrade.api._read_state", return_value={"new_signals": 1}):
            assert client.get("/api/signals").json() == {"new_signals": 1}
