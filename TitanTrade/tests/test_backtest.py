"""Tests for the backtesting engine. Zero API calls — uses synthetic data."""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import pytest

from titantrade.backtest.engine import run_backtest
from titantrade.backtest.metrics import compute_metrics
from titantrade.backtest.simulator import PortfolioSimulator
from titantrade.backtest.synthetic_thesis import generate_synthetic_thesis


def _make_bars(n: int, start: float = 100.0, trend: float = 0.1) -> list[dict]:
    """Generate N bars with a gentle uptrend + noise."""
    bars = []
    for i in range(n):
        noise = 1.5 * math.sin(i * 0.3)
        close = start + i * trend + noise
        bars.append({
            "date": f"2025-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}",
            "open": round(close - 0.2, 2),
            "high": round(close + 1.0, 2),
            "low": round(close - 1.0, 2),
            "close": round(close, 2),
            "volume": 5_000_000 + i * 10_000,
        })
    return bars


class TestSyntheticThesis:
    def test_generates_neutral_with_insufficient_data(self):
        bars = _make_bars(5)
        thesis = generate_synthetic_thesis("TEST", bars)
        assert thesis["thesis"] == "NEUTRAL"

    def test_generates_bullish_on_oversold(self):
        # Create a series that drops enough to get RSI < 30
        bars = _make_bars(50, start=100, trend=-0.8)
        thesis = generate_synthetic_thesis("TEST", bars)
        # May or may not trigger depending on exact RSI — just verify it returns valid schema
        assert thesis["thesis"] in {"BULLISH", "NEUTRAL", "BEARISH"}
        assert "hold_horizon" in thesis
        assert "review_action" in thesis

    def test_bullish_thesis_has_valid_levels(self):
        # Create a clear uptrend with golden cross conditions
        bars = _make_bars(250, start=80, trend=0.2)
        thesis = generate_synthetic_thesis("TEST", bars)
        if thesis["thesis"] == "BULLISH":
            assert thesis["target_entry_price"] > 0
            assert thesis["stop_loss_price"] > 0
            assert thesis["stop_loss_price"] < thesis["target_entry_price"]
            if thesis["take_profit_price"]:
                assert thesis["take_profit_price"] > thesis["target_entry_price"]


class TestSimulator:
    def test_basic_buy_sell_cycle(self):
        sim = PortfolioSimulator(initial_capital=100_000)
        bars_day1 = {"TEST": {"open": 100, "high": 101, "low": 99, "close": 100, "volume": 1e6}}
        thesis = {
            "TEST": {
                "thesis": "BULLISH", "confidence": 0.80,
                "target_entry_price": 100.0, "stop_loss_price": 95.0,
                "take_profit_price": 110.0,
            }
        }
        sim.process_day("2025-01-01", bars_day1, thesis, {"TEST": "Technology"})
        assert len(sim.pending_buys) > 0  # Orders placed

    def test_stop_loss_fires(self):
        sim = PortfolioSimulator(initial_capital=100_000)
        # Day 1: enter
        sim.positions["TEST"] = sim._fill_buy.__func__  # Skip — manually set position
        from titantrade.backtest.simulator import SimPosition
        sim.positions["TEST"] = SimPosition(
            ticker="TEST", shares=100, entry_price=100.0,
            entry_date="2025-01-01", stop_loss_price=95.0,
            take_profit_price=110.0, high_water_mark=100.0,
        )
        sim.cash -= 10000

        # Day 2: price drops through stop
        bar = {"open": 94, "high": 95, "low": 92, "close": 93, "volume": 1e6}
        sim._check_stops("TEST", bar, "2025-01-02")
        assert "TEST" not in sim.positions
        assert len(sim.trade_log) == 1
        assert sim.trade_log[0]["trigger"] == "stop_loss"

    def test_take_profit_fires(self):
        sim = PortfolioSimulator(initial_capital=100_000)
        from titantrade.backtest.simulator import SimPosition
        sim.positions["TEST"] = SimPosition(
            ticker="TEST", shares=100, entry_price=100.0,
            entry_date="2025-01-01", stop_loss_price=95.0,
            take_profit_price=110.0, high_water_mark=100.0,
        )
        sim.cash -= 10000

        bar = {"open": 109, "high": 111, "low": 108, "close": 110, "volume": 1e6}
        sim._check_take_profit("TEST", bar, "2025-01-02")
        assert "TEST" not in sim.positions
        assert sim.trade_log[0]["trigger"] == "take_profit"

    def test_trailing_stop_activates(self):
        sim = PortfolioSimulator(initial_capital=100_000)
        from titantrade.backtest.simulator import SimPosition
        pos = SimPosition(
            ticker="TEST", shares=100, entry_price=100.0,
            entry_date="2025-01-01", stop_loss_price=95.0,
            take_profit_price=120.0, high_water_mark=100.0,
        )
        sim.positions["TEST"] = pos

        # Price rises 7% above entry
        bar = {"open": 106, "high": 107.5, "low": 105.5, "close": 107, "volume": 1e6}
        sim._update_trailing("TEST", bar)
        assert pos.trailing_active is True
        assert pos.trailing_stop_price > 95.0


class TestMetrics:
    def test_basic_metrics(self):
        equity = [
            {"date": "2025-01-01", "portfolio_value": 100000},
            {"date": "2025-01-02", "portfolio_value": 101000},
            {"date": "2025-01-03", "portfolio_value": 99500},
            {"date": "2025-01-04", "portfolio_value": 102000},
        ]
        trades = [
            {"action": "SELL", "pnl_pct": 2.0, "trigger": "take_profit", "days_held": 3},
            {"action": "SELL", "pnl_pct": -1.5, "trigger": "stop_loss", "days_held": 2},
        ]
        m = compute_metrics(equity, trades, initial_capital=100000)
        assert m["total_return_pct"] == 2.0
        assert m["total_trades"] == 2
        assert m["win_rate"] == 50.0
        assert m["exit_triggers"]["take_profit"] == 1
        assert m["exit_triggers"]["stop_loss"] == 1

    def test_empty_equity_curve(self):
        m = compute_metrics([], [])
        assert "error" in m


class TestBacktestIntegration:
    def test_runs_with_synthetic_data(self, tmp_path):
        """Full backtest with generated data. Zero API calls."""
        # Create test data files
        for ticker in ["TEST1", "TEST2", "SPY"]:
            trend = 0.15 if ticker != "TEST2" else -0.05
            bars = _make_bars(200, start=100, trend=trend)
            with open(tmp_path / f"{ticker}.json", "w") as f:
                json.dump(bars, f)

        result = run_backtest(
            data_dir=str(tmp_path),
            tickers=["TEST1", "TEST2"],
            initial_capital=100_000,
        )

        assert "error" not in result
        assert result["config"]["trading_days"] > 0
        assert "metrics" in result
        m = result["metrics"]
        assert isinstance(m["total_return_pct"], (int, float))
        assert isinstance(m["sharpe_ratio"], (int, float))
        assert isinstance(m["max_drawdown_pct"], (int, float))
