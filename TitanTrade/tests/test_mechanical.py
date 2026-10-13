"""The mechanical strategy: signal rules, the plan, the residual core, the
backtester, the curator and the API. Zero network."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from titantrade.signals import (
    breadth, dip_state, evaluate_dip, insurance_state, rank_dips, sma, trading_days_between,
)

STARTED = "2026-10-14T12:00:00+00:00"
BEFORE = "2026-10-01T14:15:00+00:00"
AFTER = "2026-10-15T14:15:00+00:00"


def _cfg(fake_config, **kw):
    t = dict(watchlist=["AAA", "BBB", "CCC", "DDD"], max_slots=2)
    t.update(kw)
    return replace(fake_config, trading=replace(fake_config.trading, **t))


def _write(state_dir, name, data):
    (state_dir / name).write_text(json.dumps(data))


def _bundle(spy_above=True, pct=0.7, lookback=90, sma_days=150, **inputs):
    stocks = {t: {"signal_inputs": {**v, "lookback_days": lookback, "trend_sma_days": sma_days}} for t, v in inputs.items()}
    return {"generated_at": AFTER, "market_context": {"spy": {"close": 778.1}, "breadth": {"spy_above_sma": spy_above, "pct": pct}}, "stocks": stocks}


def _inp(close, high, trend):
    return {"close": close, "high_lookback": high, "sma_trend": trend}


class TestSignals:
    def test_dip_in_uptrend(self):
        assert evaluate_dip(88.0, 100.0, 85.0, dip_pct=0.08)["signal"] is True
        assert evaluate_dip(88.0, 100.0, 90.0, dip_pct=0.08)["signal"] is False      # below trend
        assert evaluate_dip(95.0, 100.0, 85.0, dip_pct=0.08)["signal"] is False      # shallow
        assert evaluate_dip(None, 100.0, 85.0, dip_pct=0.08)["dip_pct"] is None

    def test_dip_state_over_a_series(self):
        closes = [100.0] * 200 + [120.0, 105.0]
        s = dip_state(closes, dip_pct=0.10, lookback=60, trend_sma=200)
        assert s["high"] == 120.0 and s["signal"] is True and sma(closes, 200) is not None

    def test_breadth_and_two_signal_insurance(self):
        assert breadth([True, False, None, True]) == 2 / 3 and breadth([None]) is None
        assert insurance_state(True, 0.2, breadth_threshold=0.5, scale=0.5)["risk_off"] is False
        off = insurance_state(False, 0.4, breadth_threshold=0.5, scale=0.5)
        assert off["risk_off"] is True and off["exposure_scale"] == 0.5
        assert insurance_state(False, 0.6, breadth_threshold=0.5, scale=0.5)["risk_off"] is False
        assert insurance_state(None, 0.1, breadth_threshold=0.5, scale=0.5)["risk_off"] is False

    def test_rank_and_trading_days(self):
        assert rank_dips({"A": {"signal": True, "dip_pct": 0.11}, "B": {"signal": True, "dip_pct": 0.15}, "C": {"signal": False, "dip_pct": 0.2}}) == ["B", "A"]
        assert trading_days_between("2026-10-06T14:15:00+00:00", datetime(2026, 10, 13, tzinfo=timezone.utc)) == 5
        assert trading_days_between(None) == 0


class TestBuildPlan:
    def _log(self, state_dir):
        _write(state_dir, "trade_log.json", {"trades": [
            {"ticker": "EEE", "action": "BUY", "timestamp": BEFORE, "stop_price": 50.0, "target_price": 70.0, "trigger": "entry"},
            {"ticker": "BBB", "action": "BUY", "timestamp": AFTER, "stop_price": 90.0, "target_price": 120.0, "trigger": "entry"},
        ]})

    def test_hold_new_watch_and_legacy(self, fake_config, tmp_state_dir):
        from titantrade.mechanical import build_plan
        self._log(tmp_state_dir)
        cfg = _cfg(fake_config)
        bundle = _bundle(AAA=_inp(88, 100, 80), BBB=_inp(100, 100, 80), CCC=_inp(85, 100, 90), DDD=_inp(91, 100, 80))
        positions = [{"symbol": "SPY", "qty": "50"}, {"symbol": "BBB", "qty": "10", "avg_entry_price": "100"}, {"symbol": "EEE", "qty": "5", "avg_entry_price": "60"}]
        plan = build_plan(cfg, bundle, positions, set(), started_at=STARTED)
        by = {i["ticker"]: i for i in plan["items"]}
        assert by["BBB"]["action"] == "HOLD" and by["BBB"]["stop_price"] == 90.0 and by["BBB"]["target_price"] == 120.0
        assert "EEE" not in by and plan["legacy_to_close"] == ["EEE"]
        assert plan["free_slots"] == 1 and by["AAA"]["action"] == "NEW"
        assert by["AAA"]["stop_price"] == round(88 * 0.88, 2) and by["AAA"]["target_price"] == round(88 * 1.20, 2)
        watch = {w["ticker"]: w for w in plan["watch"]}
        assert "no free slot" in watch["DDD"]["reason"] and "below its 150-day SMA" in watch["CCC"]["reason"]
        assert [c["ticker"] for c in plan["candidates"]] == ["AAA", "DDD"] and plan["stale_inputs"] is False

    def test_risk_off_blocks_new_entries_but_keeps_held(self, fake_config, tmp_state_dir):
        from titantrade.mechanical import build_plan
        self._log(tmp_state_dir)
        bundle = _bundle(spy_above=False, pct=0.3, AAA=_inp(88, 100, 80), BBB=_inp(100, 100, 80), CCC=_inp(100, 100, 80), DDD=_inp(100, 100, 80))
        plan = build_plan(_cfg(fake_config), bundle, [{"symbol": "BBB", "qty": "10", "avg_entry_price": "100"}], set(), started_at=STARTED)
        assert plan["insurance"]["risk_off"] is True and plan["new_signals"] == 0
        assert [i["action"] for i in plan["items"]] == ["HOLD"]
        assert any("risk-off" in w["reason"] for w in plan["watch"] if w["ticker"] == "AAA")

    def test_pending_bracket_keeps_its_item_and_occupies_a_slot(self, fake_config, tmp_state_dir):
        from titantrade.mechanical import build_plan
        self._log(tmp_state_dir)
        bundle = _bundle(AAA=_inp(88, 100, 80), BBB=_inp(100, 100, 80), CCC=_inp(100, 100, 80), DDD=_inp(89, 100, 80))
        plan = build_plan(_cfg(fake_config, max_slots=1), bundle, [], {"DDD"}, started_at=STARTED)
        by = {i["ticker"]: i for i in plan["items"]}
        assert plan["free_slots"] == 0 and by["DDD"]["action"] == "NEW" and "AAA" not in by

    def test_stale_inputs_are_flagged(self, fake_config, tmp_state_dir, caplog):
        from titantrade.mechanical import build_plan
        self._log(tmp_state_dir)
        bundle = _bundle(lookback=60, sma_days=200, AAA=_inp(88, 100, 80), BBB=_inp(100, 100, 80), CCC=_inp(100, 100, 80), DDD=_inp(100, 100, 80))
        with caplog.at_level("WARNING"):
            plan = build_plan(_cfg(fake_config), bundle, [], set(), started_at=STARTED)
        assert plan["stale_inputs"] is True and "run `titantrade fetch`" in caplog.text

    def test_refresh_writes_plan_and_strategy_files(self, fake_config, tmp_state_dir):
        from titantrade.mechanical import refresh_plan
        self._log(tmp_state_dir)
        _write(tmp_state_dir, "data_bundle.json", _bundle(AAA=_inp(88, 100, 80), BBB=_inp(100, 100, 80), CCC=_inp(100, 100, 80), DDD=_inp(100, 100, 80)))
        with patch("titantrade.mechanical.get_positions", return_value=[]), patch("titantrade.mechanical.get_open_orders", return_value=[]):
            plan = refresh_plan(_cfg(fake_config))
        assert plan["new_signals"] == 1
        assert json.loads((tmp_state_dir / "plan.json").read_text())["items"][0]["ticker"] == "AAA"
        assert json.loads((tmp_state_dir / "strategy.json").read_text())["started_at"]


class TestCoreTarget:
    def test_residual_after_overlay_and_planned_slots(self, fake_config):
        from titantrade.mechanical import core_target_pct
        cfg = _cfg(fake_config)
        positions = [{"symbol": "SPY", "market_value": "60000"}, {"symbol": "BBB", "market_value": "20000"}]
        assert core_target_pct(cfg, 100_000, positions, planned_new_slots=1, exposure_scale=1.0) == 0.50
        assert core_target_pct(cfg, 100_000, positions, planned_new_slots=1, exposure_scale=0.5) == 0.025
        assert core_target_pct(cfg, 100_000, positions, planned_new_slots=3, exposure_scale=1.0) == 0.0


def _bars(closes, start=datetime(2024, 1, 1)):
    out = []
    d = start
    for c in closes:
        while d.weekday() >= 5:
            d += timedelta(days=1)
        out.append({"date": d.strftime("%Y-%m-%d"), "open": c, "high": c, "low": c, "close": c, "volume": 1000})
        d += timedelta(days=1)
    return out


class TestBacktest:
    def test_dip_in_uptrend_is_bought_and_exits_at_target(self):
        from titantrade.backtest.mechanical import run_mechanical_backtest
        n = 400
        spy = [100 + 0.05 * i for i in range(n)]
        aaa = [100 + 0.3 * i for i in range(300)]
        peak = aaa[-1]
        aaa += [peak * (1 - 0.03 * k) for k in range(1, 5)]
        low = aaa[-1]
        aaa += [low * (1 + 0.025 * k) for k in range(1, 9)]
        aaa += [aaa[-1]] * (n - len(aaa))
        res = run_mechanical_backtest({"AAA": _bars(aaa)}, _bars(spy), None, {"max_slots": 1})
        assert res["metrics"]["trades"] == 1 and res["trades"][0]["exit"] == "tp" and res["trades"][0]["return"] >= 0.10

    def test_insurance_scales_exposure_in_a_broad_decline(self):
        from titantrade.backtest.mechanical import run_mechanical_backtest
        spy = [100 + 0.05 * i for i in range(300)] + [115 - 0.2 * k for k in range(1, 101)]
        res = run_mechanical_backtest({"AAA": _bars(spy)}, _bars(spy), {f"X{i}": _bars(spy) for i in range(4)}, {})
        assert res["risk_off_days"] > 0 and res["avg_exposure"] < 0.95
        assert res["metrics"]["max_drawdown"] > res["spy"]["max_drawdown"]

    def test_walk_forward(self):
        from titantrade.backtest.mechanical import walk_forward
        spy = [100 + 0.05 * i for i in range(500)]
        rows = walk_forward({"AAA": _bars(spy)}, _bars(spy), None, [{"dip_pct": 0.1}, {"dip_pct": 0.2}], split="2025-01-01")
        assert len(rows) == 2 and {"in_sample", "out_of_sample"} <= rows[0].keys()


class TestCurator:
    def test_universe_review_writes_an_advisory_proposal(self, fake_config, tmp_state_dir):
        from titantrade.curator import build_universe_prompt, run_universe_review
        cfg = _cfg(fake_config)
        _write(tmp_state_dir, "data_bundle.json", _bundle(AAA=_inp(88, 100, 80)))
        _write(tmp_state_dir, "trade_log.json", {"trades": [{"ticker": "AAA", "action": "BUY", "timestamp": AFTER}]})
        system, user = build_universe_prompt(cfg, json.loads((tmp_state_dir / "data_bundle.json").read_text()), [])
        assert "AAA" in user and "JSON" in system
        reply = 'Sure: {"remove": [{"ticker": "CCC", "reason": "weak"}], "add": [{"ticker": "MSFT", "sector": "Technology", "reason": "durable"}], "notes": "ok"}'
        with patch("titantrade.curator._call_claude", return_value=reply), \
             patch("titantrade.market_data.get_news", return_value=[]), patch("titantrade.market_data.get_analyst_ratings", return_value={}), \
             patch("titantrade.notifier.send_discord") as discord:
            doc = run_universe_review(cfg)
        assert doc["proposal"]["add"][0]["ticker"] == "MSFT" and doc["status"].startswith("advisory")
        discord.assert_called_once()


class TestApi:
    def test_plan_and_proposal_endpoints(self):
        from fastapi.testclient import TestClient
        from titantrade.api import app
        client = TestClient(app)
        with patch("titantrade.api._read_state", return_value={}):
            assert client.get("/api/plan").status_code == 404
            assert client.get("/api/universe-proposal").status_code == 404
        with patch("titantrade.api._read_state", return_value={"items": []}):
            assert client.get("/api/plan").json() == {"items": []}
