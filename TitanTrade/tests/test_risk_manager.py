"""Tests for risk manager gates.

Tests all 6 gates individually and through pre_trade_check.
No API calls — all external dependencies (sector cache, state files) are mocked.

IMPORTANT: No AI tokens are spent in these tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from titantrade.risk_manager import (
    MAX_DRAWDOWN_PCT,
    MAX_SECTOR_EXPOSURE_PCT,
    MIN_CASH_RESERVE_PCT,
    MIN_CONFIDENCE,
    check_drawdown_circuit_breaker,
    check_sector_limit,
    max_investable_amount,
    passes_confidence_threshold,
    pre_trade_check,
    volatility_adjusted_shares,
)

from tests.conftest import write_state_file


# ---------------------------------------------------------------------------
# Gate 1: Confidence Threshold
# ---------------------------------------------------------------------------

class TestConfidenceGate:
    def test_passes_at_threshold(self):
        assert passes_confidence_threshold("AAPL", 0.70) is True

    def test_passes_above_threshold(self):
        assert passes_confidence_threshold("AAPL", 0.85) is True

    def test_fails_below_threshold(self):
        assert passes_confidence_threshold("AAPL", 0.69) is False

    def test_fails_at_zero(self):
        assert passes_confidence_threshold("AAPL", 0.0) is False

    def test_passes_at_one(self):
        assert passes_confidence_threshold("AAPL", 1.0) is True

    def test_custom_threshold(self):
        assert passes_confidence_threshold("AAPL", 0.50, threshold=0.50) is True
        assert passes_confidence_threshold("AAPL", 0.49, threshold=0.50) is False


# ---------------------------------------------------------------------------
# Gate 3: Drawdown Circuit Breaker
# ---------------------------------------------------------------------------

class TestDrawdownCircuitBreaker:
    def test_no_drawdown(self, tmp_state_dir: Path):
        tripped, pct = check_drawdown_circuit_breaker(100_000)
        assert tripped is False
        assert pct == 0.0

    def test_within_limit(self, tmp_state_dir: Path):
        # Set peak to 100k, test at 93k (7% drawdown, under 8% limit)
        write_state_file(tmp_state_dir, "peak_portfolio.json", {"peak_value": 100_000})
        tripped, pct = check_drawdown_circuit_breaker(93_000)
        assert tripped is False
        assert pct == 7.0

    def test_at_limit_trips(self, tmp_state_dir: Path):
        write_state_file(tmp_state_dir, "peak_portfolio.json", {"peak_value": 100_000})
        tripped, pct = check_drawdown_circuit_breaker(92_000)
        assert tripped is True
        assert pct == 8.0

    def test_beyond_limit_trips(self, tmp_state_dir: Path):
        write_state_file(tmp_state_dir, "peak_portfolio.json", {"peak_value": 100_000})
        tripped, pct = check_drawdown_circuit_breaker(85_000)
        assert tripped is True
        assert pct == 15.0

    def test_new_high_updates_peak(self, tmp_state_dir: Path):
        write_state_file(tmp_state_dir, "peak_portfolio.json", {"peak_value": 100_000})
        tripped, pct = check_drawdown_circuit_breaker(110_000)
        assert tripped is False
        assert pct == 0.0


# ---------------------------------------------------------------------------
# Gate 4: Cash Reserve
# ---------------------------------------------------------------------------

class TestCashReserve:
    def test_plenty_of_cash(self):
        # Portfolio 100k, cash 50k, reserve = 20k -> investable = 30k
        result = max_investable_amount(100_000, 50_000)
        assert result == 30_000

    def test_exactly_at_reserve(self):
        # Portfolio 100k, cash 20k, reserve = 20k -> investable = 0
        result = max_investable_amount(100_000, 20_000)
        assert result == 0

    def test_below_reserve(self):
        result = max_investable_amount(100_000, 15_000)
        assert result == 0

    def test_no_cash(self):
        result = max_investable_amount(100_000, 0)
        assert result == 0

    def test_large_portfolio(self):
        # Portfolio 1M, cash 500k, reserve = 200k -> investable = 300k
        result = max_investable_amount(1_000_000, 500_000)
        assert result == 300_000


# ---------------------------------------------------------------------------
# Gate 5: Volatility-Adjusted Position Sizing
# ---------------------------------------------------------------------------

class TestPositionSizing:
    def test_atr_based_sizing(self):
        # portfolio=100k, entry=$50, ATR=$2
        # dollar_risk = 100k * 0.02 = 2000, atr_shares = 2000/2 = 1000
        # max_position = 100k * 0.10 / 50 = 200
        # result = min(1000, 200) = 200
        shares = volatility_adjusted_shares(100_000, 50.0, 2.0, 0.10)
        assert shares == 200

    def test_atr_limits_below_max(self):
        # portfolio=100k, entry=$50, ATR=$50
        # dollar_risk = 100k * 0.02 = 2000, atr_shares = 2000/50 = 40
        # max_position = 100k * 0.10 / 50 = 200
        # result = min(40, 200) = 40
        shares = volatility_adjusted_shares(100_000, 50.0, 50.0, 0.10)
        assert shares == 40

    def test_no_atr_falls_back_to_fixed(self):
        # portfolio=100k, entry=$50, no ATR -> fixed: 100k * 0.10 / 50 = 200
        shares = volatility_adjusted_shares(100_000, 50.0, None, 0.10)
        assert shares == 200

    def test_zero_atr_falls_back(self):
        shares = volatility_adjusted_shares(100_000, 50.0, 0.0, 0.10)
        assert shares == 200

    def test_zero_entry_returns_zero(self):
        shares = volatility_adjusted_shares(100_000, 0.0, 2.0, 0.10)
        assert shares == 0


# ---------------------------------------------------------------------------
# Gate 6: Sector Exposure
# ---------------------------------------------------------------------------

class TestSectorExposure:
    def test_within_limit(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("titantrade.risk_manager.get_stock_sector", lambda t: "Technology")
        # Existing: NVDA $15k in Tech (15% of 100k)
        # Adding AAPL $10k would be 25% -> under 40% limit
        positions = [{"symbol": "NVDA", "market_value": "15000"}]
        allowed, pct = check_sector_limit("AAPL", 10_000, positions, 100_000)
        assert allowed is True

    def test_exceeds_limit(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("titantrade.risk_manager.get_stock_sector", lambda t: "Technology")
        # Existing: NVDA $35k (35%) + new $10k = 45% -> exceeds 40%
        positions = [{"symbol": "NVDA", "market_value": "35000"}]
        allowed, pct = check_sector_limit("AAPL", 10_000, positions, 100_000)
        assert allowed is False

    def test_different_sector_passes(self, monkeypatch: pytest.MonkeyPatch):
        def sector_for(t: str) -> str:
            return "Technology" if t == "NVDA" else "Healthcare"
        monkeypatch.setattr("titantrade.risk_manager.get_stock_sector", sector_for)
        positions = [{"symbol": "NVDA", "market_value": "35000"}]
        allowed, pct = check_sector_limit("LLY", 10_000, positions, 100_000)
        assert allowed is True


# ---------------------------------------------------------------------------
# pre_trade_check: Integration
# ---------------------------------------------------------------------------

class TestPreTradeCheck:
    @pytest.fixture(autouse=True)
    def _mock_sector(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("titantrade.risk_manager.get_stock_sector", lambda t: "Technology")

    def test_all_gates_pass(
        self, tmp_state_dir, fake_config, bullish_thesis, sample_positions
    ):
        result = pre_trade_check(
            ticker="AAPL",
            thesis=bullish_thesis,
            portfolio_value=100_000,
            cash_balance=50_000,
            positions=sample_positions,
            stock_atr=3.0,
            earnings_blocked=False,
            cfg=fake_config,
        )
        assert result["allowed"] is True
        assert result["shares"] > 0
        assert result["failed_gates"] == []
        assert len(result["gate_results"]) == 8

    def test_confidence_gate_fails(
        self, tmp_state_dir, fake_config, bullish_thesis, sample_positions
    ):
        bullish_thesis["confidence"] = 0.50
        result = pre_trade_check(
            ticker="AAPL",
            thesis=bullish_thesis,
            portfolio_value=100_000,
            cash_balance=50_000,
            positions=sample_positions,
            stock_atr=3.0,
            earnings_blocked=False,
            cfg=fake_config,
        )
        assert result["allowed"] is False
        assert "confidence" in result["failed_gates"]

    def test_earnings_gate_fails(
        self, tmp_state_dir, fake_config, bullish_thesis, sample_positions
    ):
        result = pre_trade_check(
            ticker="AAPL",
            thesis=bullish_thesis,
            portfolio_value=100_000,
            cash_balance=50_000,
            positions=sample_positions,
            stock_atr=3.0,
            earnings_blocked=True,
            cfg=fake_config,
        )
        assert result["allowed"] is False
        assert "earnings" in result["failed_gates"]

    def test_drawdown_gate_fails(
        self, tmp_state_dir, fake_config, bullish_thesis, sample_positions
    ):
        # Set a high peak, then test with low portfolio value
        write_state_file(tmp_state_dir, "peak_portfolio.json", {"peak_value": 200_000})
        result = pre_trade_check(
            ticker="AAPL",
            thesis=bullish_thesis,
            portfolio_value=100_000,  # 50% drawdown!
            cash_balance=50_000,
            positions=sample_positions,
            stock_atr=3.0,
            earnings_blocked=False,
            cfg=fake_config,
        )
        assert result["allowed"] is False
        assert "drawdown" in result["failed_gates"]

    def test_cash_reserve_gate_fails(
        self, tmp_state_dir, fake_config, bullish_thesis, sample_positions
    ):
        result = pre_trade_check(
            ticker="AAPL",
            thesis=bullish_thesis,
            portfolio_value=100_000,
            cash_balance=10_000,  # Below 20% reserve (20k)
            positions=sample_positions,
            stock_atr=3.0,
            earnings_blocked=False,
            cfg=fake_config,
        )
        assert result["allowed"] is False
        assert "cash_reserve" in result["failed_gates"]

    def test_all_gates_evaluated_even_on_failure(
        self, tmp_state_dir, fake_config, bullish_thesis, sample_positions
    ):
        """Even if gate 1 fails, all 6 gates should still be evaluated."""
        bullish_thesis["confidence"] = 0.10  # Gate 1 fails
        result = pre_trade_check(
            ticker="AAPL",
            thesis=bullish_thesis,
            portfolio_value=100_000,
            cash_balance=50_000,
            positions=sample_positions,
            stock_atr=3.0,
            earnings_blocked=False,
            cfg=fake_config,
        )
        assert result["allowed"] is False
        # All 6 gates should have results
        assert len(result["gate_results"]) == 8
        for gate in ("confidence", "earnings", "drawdown", "cash_reserve", "position_size", "sector_exposure"):
            assert gate in result["gate_results"]

    def test_near_miss_two_gates(
        self, tmp_state_dir, fake_config, bullish_thesis, sample_positions
    ):
        """Failing exactly 2 gates qualifies as a near-miss."""
        bullish_thesis["confidence"] = 0.50  # Gate 1 fails
        result = pre_trade_check(
            ticker="AAPL",
            thesis=bullish_thesis,
            portfolio_value=100_000,
            cash_balance=50_000,
            positions=sample_positions,
            stock_atr=3.0,
            earnings_blocked=True,  # Gate 2 fails
            cfg=fake_config,
        )
        assert result["allowed"] is False
        assert len(result["failed_gates"]) == 2

    def test_cash_reserve_dependency(
        self, tmp_state_dir, fake_config, bullish_thesis, sample_positions
    ):
        """When cash reserve fails, position_size should note the dependency."""
        result = pre_trade_check(
            ticker="AAPL",
            thesis=bullish_thesis,
            portfolio_value=100_000,
            cash_balance=5_000,  # Way below reserve
            positions=sample_positions,
            stock_atr=3.0,
            earnings_blocked=False,
            cfg=fake_config,
        )
        assert "cash_reserve" in result["failed_gates"]
        pos_detail = result["gate_results"]["position_size"]["detail"]
        assert "cash reserve" in pos_detail.lower()
