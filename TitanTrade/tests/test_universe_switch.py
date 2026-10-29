"""Decision 070: the dip sleeve on the sector ETFs, the hand-picked list as a shadow list."""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta
from unittest.mock import patch

from titantrade.config import TradingSettings

ETFS = ["XLK", "XLV", "XLF", "XLE", "XLI", "XLY", "XLB", "XLRE", "XLP", "XLU", "XLC"]
STARTED = "2026-10-13T12:43:24+00:00"
AFTER = (datetime.fromisoformat(STARTED) + timedelta(days=5)).isoformat()


def _cfg(fake_config, **kw):
    return replace(fake_config, trading=replace(fake_config.trading, **kw))


def _inp(close, high, sma):
    return {"signal_inputs": {"close": close, "high_lookback": high, "sma_trend": sma, "lookback_days": 90, "trend_sma_days": 150}}


class TestConfig:
    def test_shadow_list_and_design_are_loaded(self, tmp_path, monkeypatch):
        from titantrade.config import load_watchlist
        monkeypatch.setattr("titantrade.config.DATA_DIR", tmp_path)
        (tmp_path / "watchlist.json").write_text(json.dumps({
            "watchlist": ETFS, "shadow_watchlist": ["CRWD", "ANET"],
            "settings": {"trading_mode": "paper", "mechanical": {"design": "070", "momentum_weight": 0.6}},
        }))
        t = load_watchlist()
        assert t.watchlist == ETFS and t.shadow_watchlist == ["CRWD", "ANET"] and t.design == "070"
        assert TradingSettings().shadow_watchlist == [] and TradingSettings().design == "068"

    def test_staged_decision_070_file_is_the_live_file_with_the_switch(self):
        from pathlib import Path
        data = Path(__file__).resolve().parents[1] / "data"
        live = json.loads((data / "watchlist.json").read_text())
        staged = json.loads((data / "watchlist.decision070.json").read_text())
        assert staged["watchlist"] == ETFS and staged["shadow_watchlist"] == live["watchlist"]
        assert {k: v for k, v in staged["settings"]["mechanical"].items() if k != "design"} == live["settings"]["mechanical"]
        assert staged["settings"]["mechanical"]["design"] == "070"


class TestPlan:
    def _log(self, state_dir):
        (state_dir / "trade_log.json").write_text(json.dumps({"trades": [
            {"ticker": "DXCM", "action": "BUY", "timestamp": AFTER, "stop_price": 68.91, "target_price": 93.96, "trigger": "entry"},
        ]}))

    def test_held_name_removed_from_the_watchlist_keeps_its_hold_item(self, fake_config, tmp_state_dir):
        from titantrade.mechanical import build_plan
        self._log(tmp_state_dir)
        cfg = _cfg(fake_config, watchlist=ETFS, momentum_weight=0.6)
        bundle = {"stocks": {e: _inp(100, 100, 80) for e in ETFS}, "market_context": {}}
        positions = [{"symbol": "SPMO", "qty": "216"}, {"symbol": "DXCM", "qty": "325", "avg_entry_price": "78.08"}]
        plan = build_plan(cfg, bundle, positions, set(), started_at=STARTED)
        by = {i["ticker"]: i for i in plan["items"]}
        assert by["DXCM"]["action"] == "HOLD" and by["DXCM"]["stop_price"] == 68.91   # managed to its own exit, no orphan close
        assert plan["legacy_to_close"] == [] and plan["held"] == ["DXCM"] and plan["free_slots"] == 2
        assert "DXCM" not in {c["ticker"] for c in plan["candidates"]}                  # and never a new entry

    def test_a_pre_strategy_position_off_the_watchlist_is_still_legacy(self, fake_config, tmp_state_dir):
        from titantrade.mechanical import build_plan
        (tmp_state_dir / "trade_log.json").write_text(json.dumps({"trades": []}))
        cfg = _cfg(fake_config, watchlist=ETFS)
        plan = build_plan(cfg, {"stocks": {}, "market_context": {}}, [{"symbol": "OLD", "qty": "5"}], set(), started_at=STARTED)
        assert plan["legacy_to_close"] == ["OLD"]

    def test_design_change_restamps_the_window_once(self, fake_config, tmp_state_dir):
        from titantrade.mechanical import benchmark_window_start, refresh_plan
        (tmp_state_dir / "trade_log.json").write_text(json.dumps({"trades": []}))
        (tmp_state_dir / "strategy.json").write_text(json.dumps({"strategy": "mechanical", "started_at": STARTED, "decision": "061",
                                                                 "window_started_at": "2026-10-27T17:32:42+00:00", "design": "068"}))
        (tmp_state_dir / "data_bundle.json").write_text(json.dumps({"stocks": {e: _inp(100, 100, 80) for e in ETFS}, "market_context": {}}))
        with patch("titantrade.mechanical.get_positions", return_value=[]), patch("titantrade.mechanical.get_open_orders", return_value=[]):
            refresh_plan(_cfg(fake_config, watchlist=ETFS, momentum_weight=0.6, design="070"))
            doc = json.loads((tmp_state_dir / "strategy.json").read_text())
            refresh_plan(_cfg(fake_config, watchlist=ETFS, momentum_weight=0.6, design="070"))
        assert doc["design"] == "070" and doc["window_started_at"] > "2026-10-27T17:32:42+00:00" and doc["started_at"] == STARTED
        assert doc["dip_universe"] == ETFS
        assert json.loads((tmp_state_dir / "strategy.json").read_text())["window_started_at"] == doc["window_started_at"]
        assert benchmark_window_start() == doc["window_started_at"]


class TestGatesOnETFs:
    def test_sector_etfs_carry_their_sector_without_finnhub(self, fake_config, tmp_state_dir, monkeypatch):
        from titantrade import market_context as mc
        monkeypatch.setattr(mc, "_sector_cache", {})
        monkeypatch.setattr(mc, "_sector_cache_path", lambda: tmp_state_dir / "sector_cache.json")
        with patch("titantrade.market_context.market_data.get_sector", return_value="Unknown") as finnhub:
            sectors = mc.load_stock_sectors(["XLK", "XLE", "AAPL"], fake_config)
        assert sectors["XLK"] == "Technology" and sectors["XLE"] == "Energy"
        finnhub.assert_called_once_with("AAPL", fake_config)

    def test_correlation_gate_skips_sector_etfs(self, fake_config, tmp_state_dir):
        from titantrade.risk_manager import pre_trade_check
        matrix = {"XLY": {"XLK": 0.9}, "AAA": {"XLK": 0.9}}
        held = [{"symbol": "XLK", "qty": "100", "market_value": "10000"}]
        kw = dict(portfolio_value=100_000, cash_balance=50_000, positions=held, earnings_blocked=False, correlation_matrix=matrix)
        cfg = _cfg(fake_config, watchlist=ETFS + ["AAA"])
        etf = pre_trade_check(ticker="XLY", item={"ticker": "XLY", "entry_price": 100.0, "stop_price": 88.0}, cfg=cfg, **kw)
        name = pre_trade_check(ticker="AAA", item={"ticker": "AAA", "entry_price": 100.0, "stop_price": 88.0}, cfg=cfg, **kw)
        assert etf["gate_results"]["correlation"]["passed"] is True and "not applied" in etf["gate_results"]["correlation"]["detail"]
        assert name["gate_results"]["correlation"]["passed"] is False


class TestShadowList:
    def test_bundle_fetches_the_shadow_names_too(self, fake_config):
        from titantrade.data_fetcher import bundle_names
        cfg = _cfg(fake_config, watchlist=ETFS, shadow_watchlist=["CRWD", "XLK"])
        assert bundle_names(cfg) == ETFS + ["CRWD"]

    def test_curator_works_on_the_shadow_list(self, fake_config, tmp_state_dir):
        from titantrade import curator
        cfg = _cfg(fake_config, watchlist=ETFS, shadow_watchlist=["CRWD", "ANET"])
        _, user = curator.build_universe_prompt(cfg, {"stocks": {}}, [])
        assert [b["ticker"] for b in json.loads(user)["watchlist"]] == ["CRWD", "ANET"]
        (tmp_state_dir / "data_bundle.json").write_text(json.dumps({"stocks": {}}))
        with patch("titantrade.curator._call_claude", return_value='{"remove": [], "add": [], "notes": "ok"}'), \
             patch("titantrade.curator.send_discord", create=True), patch("titantrade.curator._trades", return_value=[]):
            doc = curator.run_universe_review(cfg)
        assert doc["watchlist"] == ["CRWD", "ANET"] and doc["list"] == "shadow_watchlist" and "shadow" in doc["status"]

    def test_backtest_shadow_flag_runs_the_shadow_list(self, fake_config, capsys):
        from titantrade.backtest import mechanical as bt
        cfg = _cfg(fake_config, watchlist=ETFS, shadow_watchlist=["CRWD", "ANET"])
        seen = {}

        def fake_load(tickers, data_dir, *a, **k):
            seen["tickers"] = tickers
            return {}
        with patch("titantrade.config.load_config", return_value=cfg), patch("titantrade.backtest.mechanical.load_historical_data", side_effect=fake_load), \
             patch("titantrade.backtest.mechanical.run_mechanical_backtest", return_value={"error": "no data"}):
            bt.main(["--shadow"])
        assert seen["tickers"][:2] == ["CRWD", "ANET"] and "SPY" in seen["tickers"]
        with patch("titantrade.config.load_config", return_value=_cfg(fake_config, watchlist=ETFS)):
            bt.main(["--shadow"])
        assert "No shadow_watchlist" in capsys.readouterr().out
