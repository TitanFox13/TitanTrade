"""The eight risk gates and the slot sizing."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from titantrade.risk_manager import (
    MAX_DRAWDOWN_PCT, MAX_TOTAL_OVERLAY_PCT, MIN_CASH_RESERVE_PCT, MIN_POSITION_NOTIONAL,
    SUSPECT_VALUE_DEVIATION_PCT, check_correlation_limit, check_drawdown_circuit_breaker,
    check_macro_blackout, compute_overlay_headroom, max_investable_amount, pre_trade_check,
    update_peak_value,
)


def _item(entry=100.0, ticker="AAA"):
    return {"ticker": ticker, "entry_price": entry, "stop_price": entry * 0.88, "target_price": entry * 1.2}


@pytest.fixture(autouse=True)
def _sector(monkeypatch):
    monkeypatch.setattr("titantrade.risk_manager.get_stock_sector", lambda t: "ETF" if t == "SPY" else "Technology")


class TestDrawdownBreaker:
    def test_trips_at_limit_and_tracks_peak(self, tmp_state_dir):
        assert check_drawdown_circuit_breaker(100_000) == (False, 0.0)
        tripped, dd = check_drawdown_circuit_breaker(100_000 * (1 - MAX_DRAWDOWN_PCT / 100))
        assert tripped and dd == pytest.approx(MAX_DRAWDOWN_PCT)
        assert check_drawdown_circuit_breaker(110_000) == (False, 0.0)   # new high

    def test_suspect_values_block_but_never_corrupt_the_peak(self, tmp_state_dir):
        update_peak_value(100_000)
        tripped, dd = check_drawdown_circuit_breaker(100_000 * (1 - SUSPECT_VALUE_DEVIATION_PCT / 100) * 0.9)
        assert tripped and dd > SUSPECT_VALUE_DEVIATION_PCT
        assert update_peak_value(100_000 * 2) == 100_000                 # spike refused
        assert json.loads((tmp_state_dir / "peak_portfolio.json").read_text())["peak_value"] == 100_000


class TestCashReserve:
    def test_reserve_and_committed_cash(self):
        assert max_investable_amount(100_000, 20_000) == 20_000 - 100_000 * MIN_CASH_RESERVE_PCT / 100
        assert max_investable_amount(100_000, 5_000) == 0
        assert max_investable_amount(100_000, 20_000, committed_cash=16_000) == 0


class TestOverlayCap:
    def test_headroom_excludes_core(self):
        positions = [{"symbol": "SPY", "market_value": "50000"}, {"symbol": "AAA", "market_value": "30000"}]
        assert compute_overlay_headroom(positions, 100_000, core_tickers=("SPY",)) == 100_000 * MAX_TOTAL_OVERLAY_PCT - 30_000
        assert compute_overlay_headroom([{"symbol": "AAA", "market_value": "80000"}], 100_000) == 0


class TestMacroAndCorrelation:
    def test_only_high_impact_events_block(self):
        soon = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        assert check_macro_blackout([{"date": soon, "event": "FOMC rate decision"}])[0] is True
        assert check_macro_blackout([{"date": soon, "event": "Atlanta Fed GDPNow"}])[0] is False
        far = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        assert check_macro_blackout([{"date": far, "event": "CPI YoY"}])[0] is False

    def test_correlation_limit(self):
        matrix = {"AAA": {"BBB": 0.9, "CCC": 0.7}}
        assert check_correlation_limit("AAA", ["BBB"], matrix)[0] is False
        assert check_correlation_limit("AAA", ["CCC"], matrix)[0] is True
        assert check_correlation_limit("AAA", [], matrix) == (True, 0.0)


class TestPreTradeCheck:
    def test_all_gates_pass_with_slot_sizing(self, fake_config, tmp_state_dir):
        check = pre_trade_check("AAA", _item(100.0), 100_000, 60_000, [], earnings_blocked=False, cfg=fake_config)
        assert check["allowed"] and check["shares"] == 250.0            # 25% slot
        assert set(check["gate_results"]) == {"earnings", "drawdown", "cash_reserve", "overlay_cap", "position_size", "sector_exposure", "macro_blackout", "correlation"}

    def test_cash_and_overlay_reduce_the_slot(self, fake_config, tmp_state_dir, monkeypatch):
        check = pre_trade_check("AAA", _item(100.0), 100_000, 15_000, [], earnings_blocked=False, cfg=fake_config)
        assert check["allowed"] and check["shares"] == 100.0            # $15k − 5% reserve = $10k
        monkeypatch.setattr("titantrade.risk_manager.get_stock_sector", lambda t: {"SPY": "ETF", "BBB": "Financials"}.get(t, "Technology"))
        positions = [{"symbol": "SPY", "market_value": "30000"}, {"symbol": "BBB", "market_value": "60000"}]
        check = pre_trade_check("CCC", _item(100.0), 100_000, 60_000, positions, earnings_blocked=False, cfg=fake_config)
        assert check["allowed"] and check["shares"] == 100.0            # 70% cap − 60% held = $10k headroom

    def test_every_gate_is_evaluated_and_dust_is_blocked(self, fake_config, tmp_state_dir):
        check = pre_trade_check("AAA", _item(100.0), 100_000, 5_300, [], earnings_blocked=True, cfg=fake_config)
        assert not check["allowed"]
        assert "earnings" in check["failed_gates"] and "position_size" in check["failed_gates"]
        assert check["gate_results"]["position_size"]["detail"].startswith("Position $300 below")
        assert MIN_POSITION_NOTIONAL == 500.0

    def test_sector_cap(self, fake_config, tmp_state_dir):
        positions = [{"symbol": "BBB", "market_value": "45000"}]           # Technology already 45%
        check = pre_trade_check("AAA", _item(100.0), 100_000, 60_000, positions, earnings_blocked=False, cfg=fake_config)
        assert "sector_exposure" in check["failed_gates"]
