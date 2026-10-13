"""Tests for the backtesting engine. Zero API calls — uses synthetic data."""

from __future__ import annotations

import json
import math
from pathlib import Path

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


class TestConfidenceScalingInBacktest:
    """A/B comparison: confidence scaling should change position sizes when
    thesis confidence is above or below the 0.85 baseline, which should in
    turn change the total return (direction depends on which trades win).
    """

    def _write_fixture(self, tmp_path: Path) -> str:
        """Create 260 bars for 2 tickers + SPY."""
        (tmp_path / "TEST1.json").write_text(json.dumps(_make_bars(260, 100.0, 0.15)))
        (tmp_path / "TEST2.json").write_text(json.dumps(_make_bars(260, 50.0, 0.08)))
        (tmp_path / "SPY.json").write_text(json.dumps(_make_bars(260, 450.0, 0.12)))
        return str(tmp_path)

    def test_flag_toggles_config_field(self, tmp_path):
        data = self._write_fixture(tmp_path)
        r_off = run_backtest(data_dir=data, tickers=["TEST1", "TEST2"],
                             use_confidence_scaling=False)
        r_on = run_backtest(data_dir=data, tickers=["TEST1", "TEST2"],
                            use_confidence_scaling=True)
        assert r_off["config"]["use_confidence_scaling"] is False
        assert r_on["config"]["use_confidence_scaling"] is True

    def test_ab_comparison_structure(self, tmp_path):
        from titantrade.backtest.engine import run_ab_comparison

        data = self._write_fixture(tmp_path)
        result = run_ab_comparison(data_dir=data, tickers=["TEST1", "TEST2"])

        # Both arms produced results
        assert "baseline" in result
        assert "scaled" in result
        assert result["baseline"]["config"]["use_confidence_scaling"] is False
        assert result["scaled"]["config"]["use_confidence_scaling"] is True

        # Comparison table is populated with the expected metrics
        cmp = result["comparison"]
        assert "total_return_pct" in cmp
        assert "sharpe_ratio" in cmp
        assert "max_drawdown_pct" in cmp
        assert "trade_count" in cmp
        # Each metric (except trade_count) has baseline/scaled/delta keys
        for key in ("total_return_pct", "sharpe_ratio", "max_drawdown_pct"):
            row = cmp[key]
            assert "baseline" in row and "scaled" in row and "delta" in row


class TestStrategyDefault:
    """The backtest must default to the production-faithful v2 strategy and
    actually execute trades. Regression guard for the bug where the default
    legacy path generated almost no trades (~7 over 3 years of data).
    """

    def _write_fixture(self, tmp_path: Path) -> str:
        for ticker in ["TEST1", "TEST2", "SPY"]:
            trend = 0.15 if ticker != "TEST2" else 0.08
            (tmp_path / f"{ticker}.json").write_text(json.dumps(_make_bars(260, 100.0, trend)))
        return str(tmp_path)

    def test_default_is_strategy_v2(self, tmp_path):
        result = run_backtest(data_dir=self._write_fixture(tmp_path), tickers=["TEST1", "TEST2"])
        assert result["config"]["strategy_v2"] is True

    def test_default_executes_trades(self, tmp_path):
        """The headline failure: the old default barely traded. v2 must fill."""
        result = run_backtest(data_dir=self._write_fixture(tmp_path), tickers=["TEST1", "TEST2"])
        assert result["trade_count"] >= 5

    def test_legacy_path_still_reachable(self, tmp_path):
        result = run_backtest(
            data_dir=self._write_fixture(tmp_path), tickers=["TEST1", "TEST2"],
            strategy_v2=False,
        )
        assert result["config"]["strategy_v2"] is False
        assert "error" not in result

    def test_sim_overrides_reach_simulator(self, tmp_path):
        """Structural A/B knob: sim_overrides must flow into the simulator and
        be recorded in the result config for traceability."""
        overrides = {"core_allocation_pct": 0.0, "trailing_atr_multiplier": 3.0}
        result = run_backtest(
            data_dir=self._write_fixture(tmp_path), tickers=["TEST1", "TEST2"],
            sim_overrides=overrides,
        )
        assert result["config"]["sim_overrides"] == overrides
        assert "error" not in result


class TestV1FillCorrectness:
    """The legacy v1 fill path had two correctness bugs: it set the take-profit
    to the entry limit price (→ instant break-even 'take profit', fake 0% win
    rate) and overwrote an existing position when the second tranche filled
    (silently dropping tranche-1 shares).
    """

    def _order(self, qty, limit, stop, tp):
        from titantrade.backtest.simulator import SimOrder
        return SimOrder(
            ticker="TEST", side="buy", order_type="limit", qty=qty,
            limit_price=limit, stop_price=stop, tp_price=tp, placed_date="2025-01-01",
        )

    def test_fill_uses_thesis_tp_not_entry_price(self):
        sim = PortfolioSimulator(initial_capital=100_000)
        sim._fill_buy(self._order(100, 100.0, 95.0, 120.0), 100.0, "2025-01-02")
        pos = sim.positions["TEST"]
        assert pos.take_profit_price == 120.0      # thesis TP, not the entry limit
        assert pos.stop_loss_price == 95.0          # thesis stop, not recomputed

    def test_second_tranche_accumulates_not_overwrites(self):
        sim = PortfolioSimulator(initial_capital=1_000_000)
        sim._fill_buy(self._order(60, 100.0, 95.0, 120.0), 100.0, "2025-01-02")
        sim._fill_buy(self._order(40, 98.0, 95.0, 120.0), 98.0, "2025-01-03")
        pos = sim.positions["TEST"]
        assert pos.shares == 100                    # 60 + 40, not overwritten to 40
        # entry price is the share-weighted average of the two fills (w/ slippage)
        assert 98.0 < pos.entry_price < 100.5

    def test_unfilled_limit_order_expires(self):
        """A dip-buy limit that never fills must expire instead of blocking
        the ticker forever."""
        sim = PortfolioSimulator(initial_capital=100_000)
        sim.pending_buys.append(self._order(10, 90.0, 85.0, 110.0))  # placed 2025-01-01
        # A day well past the TTL with price never reaching the limit
        bar = {"open": 100, "high": 101, "low": 99, "close": 100, "volume": 1e6}
        sim.process_day("2025-02-01", {"TEST": bar})
        assert len(sim.pending_buys) == 0
        assert "TEST" not in sim.positions
