"""Tests for risk manager gates.

Tests all 6 gates individually and through pre_trade_check.
No API calls — all external dependencies (sector cache, state files) are mocked.

IMPORTANT: No AI tokens are spent in these tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from titantrade.risk_manager import (
    check_drawdown_circuit_breaker,
    check_sector_limit,
    confidence_scaled_risk,
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
        # MIN_CONFIDENCE is now 0.55 (was 0.70). 0.55 should pass.
        assert passes_confidence_threshold("AAPL", 0.55) is True

    def test_passes_above_threshold(self):
        assert passes_confidence_threshold("AAPL", 0.85) is True

    def test_fails_below_threshold(self):
        # Floor lowered to 0.55 (was 0.70). Anything below now fails.
        assert passes_confidence_threshold("AAPL", 0.50) is False

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
    # Reserve floor lowered from 20% to 5%: cash is now treated as transit
    # capital, not a strategic destination. The whole reason we redesigned
    # the strategy: in a rising market, the 20% floor was creating ~80% cash
    # drag in combination with the (also-removed) confidence gate.
    def test_plenty_of_cash(self):
        # Portfolio 100k, cash 50k, reserve = 5k -> investable = 45k
        result = max_investable_amount(100_000, 50_000)
        assert result == 45_000

    def test_exactly_at_reserve(self):
        # Portfolio 100k, cash 5k, reserve = 5k -> investable = 0
        result = max_investable_amount(100_000, 5_000)
        assert result == 0

    def test_below_reserve(self):
        # Portfolio 100k, cash 4k < 5k reserve -> investable = 0
        result = max_investable_amount(100_000, 4_000)
        assert result == 0

    def test_no_cash(self):
        result = max_investable_amount(100_000, 0)
        assert result == 0

    def test_large_portfolio(self):
        # Portfolio 1M, cash 500k, reserve = 50k -> investable = 450k
        result = max_investable_amount(1_000_000, 500_000)
        assert result == 450_000

    def test_committed_cash_reduces_investable(self):
        # FIX: cash already committed to pending (unfilled) buy orders must be
        # netted out, else simultaneous brackets over-commit into margin.
        # 50k cash, 5k reserve, 30k committed to pending buys -> 15k investable.
        result = max_investable_amount(100_000, 50_000, committed_cash=30_000)
        assert result == 15_000

    def test_committed_cash_can_zero_out_investable(self):
        # Pending commitments that exceed free cash leave nothing to deploy —
        # this is what prevents the account from going negative/margin.
        result = max_investable_amount(100_000, 50_000, committed_cash=46_000)
        assert result == 0

    def test_committed_cash_defaults_to_zero(self):
        # Backwards compatible: omitting committed_cash behaves as before.
        assert max_investable_amount(100_000, 50_000) == 45_000


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
        # ATR_RISK_BUDGET=0.025 (was 0.02): dollar_risk = 100k*0.025 = 2500
        # atr_shares = 2500/50 = 50
        # max_position = 100k * 0.10 / 50 = 200 (no confidence param → no scaling)
        # result = min(50, 200) = 50
        shares = volatility_adjusted_shares(100_000, 50.0, 50.0, 0.10)
        assert shares == 50

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
        # Sector cap loosened from 40% to 50% to allow tighter concentration
        # on high-conviction sectors. NVDA $45k + new $10k = 55% > 50% → fails.
        positions = [{"symbol": "NVDA", "market_value": "45000"}]
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
# Overlay-sleeve cap (defends the always-on core allocation)
# ---------------------------------------------------------------------------

class TestOverlayCap:
    """The overlay cap prevents the AI-pick sleeve from blowing past
    MAX_TOTAL_OVERLAY_PCT (70% by default), which would starve the SPY core
    allocation and rebalancing buffer.
    """

    def test_no_positions_full_headroom(self):
        from titantrade.risk_manager import compute_overlay_headroom, MAX_TOTAL_OVERLAY_PCT
        # No positions → full 70% headroom on $100k = $70k
        assert compute_overlay_headroom([], 100_000) == 100_000 * MAX_TOTAL_OVERLAY_PCT

    def test_core_ticker_excluded(self):
        from titantrade.risk_manager import compute_overlay_headroom, MAX_TOTAL_OVERLAY_PCT
        positions = [{"symbol": "SPY", "market_value": "30000"}]
        # SPY is core, shouldn't count against overlay cap
        headroom = compute_overlay_headroom(positions, 100_000, core_tickers=("SPY",))
        assert headroom == 100_000 * MAX_TOTAL_OVERLAY_PCT

    def test_existing_overlays_reduce_headroom(self):
        from titantrade.risk_manager import compute_overlay_headroom, MAX_TOTAL_OVERLAY_PCT
        positions = [
            {"symbol": "AAPL", "market_value": "20000"},
            {"symbol": "NVDA", "market_value": "15000"},
        ]
        # Overlay = 35k, cap = 70k, headroom = 35k
        headroom = compute_overlay_headroom(positions, 100_000, core_tickers=("SPY",))
        assert headroom == pytest.approx(100_000 * MAX_TOTAL_OVERLAY_PCT - 35_000)

    def test_at_cap_zero_headroom(self):
        from titantrade.risk_manager import compute_overlay_headroom, MAX_TOTAL_OVERLAY_PCT
        positions = [{"symbol": "AAPL", "market_value": str(100_000 * MAX_TOTAL_OVERLAY_PCT)}]
        assert compute_overlay_headroom(positions, 100_000, core_tickers=("SPY",)) == 0.0

    def test_above_cap_clamps_to_zero(self):
        from titantrade.risk_manager import compute_overlay_headroom
        # Overlay = 80k, cap = 70k. Don't return negative — clamp.
        positions = [{"symbol": "AAPL", "market_value": "80000"}]
        assert compute_overlay_headroom(positions, 100_000, core_tickers=("SPY",)) == 0.0


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
        # 9 gates now: confidence, earnings, drawdown, cash_reserve, overlay_cap,
        # position_size, sector_exposure, macro_blackout, correlation
        assert len(result["gate_results"]) == 9

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
        # Cash reserve floor is now 5%. A $4k cash balance against a $100k
        # portfolio is below the 5% reserve.
        result = pre_trade_check(
            ticker="AAPL",
            thesis=bullish_thesis,
            portfolio_value=100_000,
            cash_balance=4_000,  # Below 5% reserve (5k)
            positions=sample_positions,
            stock_atr=3.0,
            earnings_blocked=False,
            cfg=fake_config,
        )
        assert result["allowed"] is False
        assert "cash_reserve" in result["failed_gates"]

    def test_committed_cash_fails_reserve_gate(
        self, tmp_state_dir, fake_config, bullish_thesis, sample_positions
    ):
        """FIX: $50k cash looks deployable, but if $46k is already committed to
        pending buy orders only $4k is truly free — below the 5% reserve. The
        gate must fail so we don't stack entries into margin/negative cash.
        """
        result = pre_trade_check(
            ticker="AAPL",
            thesis=bullish_thesis,
            portfolio_value=100_000,
            cash_balance=50_000,
            positions=sample_positions,
            stock_atr=3.0,
            earnings_blocked=False,
            cfg=fake_config,
            committed_cash=46_000,
        )
        assert result["allowed"] is False
        assert "cash_reserve" in result["failed_gates"]
        assert "committed" in result["gate_results"]["cash_reserve"]["detail"]

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
        # 9 gates now: confidence, earnings, drawdown, cash_reserve, overlay_cap,
        # position_size, sector_exposure, macro_blackout, correlation
        assert len(result["gate_results"]) == 9
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


# ---------------------------------------------------------------------------
# Confidence-Scaled Risk
# ---------------------------------------------------------------------------

class TestVixScaledRisk:
    """VIX-aware risk scaling. Big position sizes in calm markets, defensive
    sizes in stressed ones. Orthogonal to confidence scaling.
    """

    def test_low_vix_amplifies(self):
        from titantrade.risk_manager import vix_scaled_risk
        # VIX < 15 → 1.2x
        assert vix_scaled_risk(0.10, 12) == pytest.approx(0.12, abs=0.001)

    def test_normal_vix_unchanged_at_25(self):
        from titantrade.risk_manager import vix_scaled_risk
        # VIX = 25 → exactly 1.0x (boundary of normal/elevated)
        assert vix_scaled_risk(0.10, 25) == pytest.approx(0.10, abs=0.001)

    def test_normal_vix_interp_at_20(self):
        from titantrade.risk_manager import vix_scaled_risk
        # VIX = 20 (mid normal) → 1.1x via linear interp 15→25
        assert vix_scaled_risk(0.10, 20) == pytest.approx(0.11, abs=0.001)

    def test_elevated_vix_trims(self):
        from titantrade.risk_manager import vix_scaled_risk
        # VIX = 30 → 0.85x (midpoint 25→35)
        assert vix_scaled_risk(0.10, 30) == pytest.approx(0.085, abs=0.001)

    def test_high_vix_defensive(self):
        from titantrade.risk_manager import vix_scaled_risk
        # VIX = 50 → 0.4x cap
        assert vix_scaled_risk(0.10, 50) == pytest.approx(0.04, abs=0.001)

    def test_extreme_vix_clamps_to_floor(self):
        from titantrade.risk_manager import vix_scaled_risk
        # VIX > 50 → still 0.4x (don't go lower)
        assert vix_scaled_risk(0.10, 80) == pytest.approx(0.04, abs=0.001)

    def test_no_vix_no_scaling(self):
        from titantrade.risk_manager import vix_scaled_risk
        # Missing VIX → don't penalize sizing
        assert vix_scaled_risk(0.10, None) == 0.10
        assert vix_scaled_risk(0.10, 0) == 0.10  # invalid VIX too

    def test_monotonically_decreasing_above_15(self):
        """Sanity: scaling must NOT increase as VIX rises past 15."""
        from titantrade.risk_manager import vix_scaled_risk
        prev = 1.0e9
        for v in [16, 20, 25, 28, 32, 35, 40, 50]:
            cur = vix_scaled_risk(0.10, v)
            assert cur <= prev, f"Non-monotonic at VIX={v}: {prev} -> {cur}"
            prev = cur


class TestConfidenceScaledRisk:
    """The new piecewise curve has anchor points at 0.55/0.65/0.70/0.80/0.90/0.95.
    Below 0.55 clamps to the floor; above 0.95 caps at 2.5x. The whole point:
    let high-conviction theses take real positions, not tokens.
    """

    def test_floor_confidence(self):
        # 0.55 (floor) -> multiplier 0.40 -> 10% * 0.40 = 4%
        assert confidence_scaled_risk(0.10, 0.55) == pytest.approx(0.04, abs=0.001)

    def test_legacy_baseline_confidence(self):
        # 0.70 (old min) -> multiplier 1.00 -> 10% * 1.00 = 10% — preserves
        # the old "baseline" risk so a 0.70 thesis is sized the same as before.
        assert confidence_scaled_risk(0.10, 0.70) == pytest.approx(0.10, abs=0.001)

    def test_strong_confidence(self):
        # 0.80 -> multiplier 1.50 -> 10% * 1.50 = 15%
        assert confidence_scaled_risk(0.10, 0.80) == pytest.approx(0.15, abs=0.001)

    def test_very_high_confidence(self):
        # 0.90 -> multiplier 2.00 -> 10% * 2.00 = 20%
        assert confidence_scaled_risk(0.10, 0.90) == pytest.approx(0.20, abs=0.001)

    def test_max_confidence_caps(self):
        # 0.95+ -> multiplier 2.50 -> 10% * 2.50 = 25%
        assert confidence_scaled_risk(0.10, 0.95) == pytest.approx(0.25, abs=0.001)
        assert confidence_scaled_risk(0.10, 1.00) == pytest.approx(0.25, abs=0.001)

    def test_mid_range_interpolation(self):
        # 0.85 sits between (0.80, 1.50) and (0.90, 2.00): mult = 1.75
        assert confidence_scaled_risk(0.10, 0.85) == pytest.approx(0.175, abs=0.001)

    def test_clamped_below_min(self):
        # Below the floor clamps to the floor's value (0.40 multiplier)
        assert confidence_scaled_risk(0.10, 0.50) == pytest.approx(0.04, abs=0.001)

    def test_clamped_above_max(self):
        # Above 1.0 clamps to the 0.95 cap (2.50 multiplier)
        assert confidence_scaled_risk(0.10, 1.50) == pytest.approx(0.25, abs=0.001)

    def test_monotonic_in_confidence(self):
        """Sanity: the curve must be non-decreasing across the input range.
        If this ever fails we've introduced a fold that would penalize higher
        confidence — a strategic bug we must never ship.
        """
        prev = -1.0
        for c in [0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00]:
            cur = confidence_scaled_risk(0.10, c)
            assert cur >= prev, f"Non-monotonic at conf={c}: {prev} -> {cur}"
            prev = cur


class TestConfidenceAwareSizing:
    def test_no_confidence_unchanged(self):
        """Without confidence param, sizing is identical to pre-existing behavior
        (no confidence scaling, just the raw risk_per_trade_pct).
        """
        shares = volatility_adjusted_shares(100_000, 50.0, 2.0, 0.10)
        assert shares == 200  # Same as TestPositionSizing.test_atr_based_sizing

    def test_high_confidence_more_shares(self):
        """confidence=0.95 should produce dramatically more shares than baseline
        — the whole strategic point. Old curve: only 1.3x. New curve: 2.5x.
        """
        baseline = volatility_adjusted_shares(100_000, 50.0, 2.0, 0.10)
        high_conf = volatility_adjusted_shares(100_000, 50.0, 2.0, 0.10, confidence=0.95)
        assert high_conf > baseline
        # And meaningfully so — at least 2x more
        assert high_conf >= baseline * 2

    def test_low_confidence_fewer_shares(self):
        """confidence=0.55 (the new floor) should produce a tiny probe — fewer
        shares than baseline. This is the "we hear you but don't size up yet"
        position.
        """
        baseline = volatility_adjusted_shares(100_000, 50.0, 2.0, 0.10)
        low_conf = volatility_adjusted_shares(100_000, 50.0, 2.0, 0.10, confidence=0.55)
        assert low_conf < baseline
        # Floor multiplier is 0.40 → ~40% of baseline
        assert low_conf <= baseline * 0.5

    def test_confidence_flows_through_pre_trade_check(
        self, monkeypatch, tmp_state_dir, fake_config, bullish_thesis, sample_positions
    ):
        """Higher confidence should result in more shares through pre_trade_check."""
        monkeypatch.setattr("titantrade.risk_manager.get_stock_sector", lambda t: "Technology")

        bullish_thesis["confidence"] = 0.72
        result_low = pre_trade_check(
            ticker="AAPL", thesis=bullish_thesis, portfolio_value=100_000,
            cash_balance=50_000, positions=sample_positions, stock_atr=3.0,
            earnings_blocked=False, cfg=fake_config,
        )

        bullish_thesis["confidence"] = 0.95
        result_high = pre_trade_check(
            ticker="AAPL", thesis=bullish_thesis, portfolio_value=100_000,
            cash_balance=50_000, positions=sample_positions, stock_atr=3.0,
            earnings_blocked=False, cfg=fake_config,
        )

        assert result_low["allowed"] is True
        assert result_high["allowed"] is True
        assert result_high["shares"] > result_low["shares"]


# ---------------------------------------------------------------------------
# Macro-blackout narrowing (#2)
# ---------------------------------------------------------------------------

class TestMacroBlackoutHighImpactOnly:
    def test_high_impact_event_blocks(self):
        from titantrade.risk_manager import check_macro_blackout
        import datetime as dt
        soon = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=3)).isoformat()
        cal = [{"date": soon, "event": "CPI YoY (May)"}]
        blocked, name = check_macro_blackout(cal)
        assert blocked is True
        assert "CPI" in name

    def test_low_impact_event_does_NOT_block(self):
        """Atlanta Fed GDPNow, CB Employment Trends Index, retail-ex-autos
        breakdowns etc. used to wrongly trigger the 24h blackout. After the
        fix they're ignored.
        """
        from titantrade.risk_manager import check_macro_blackout
        import datetime as dt
        soon = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=3)).isoformat()
        cal = [
            {"date": soon, "event": "Atlanta Fed GDPNow (Q2)"},
            {"date": soon, "event": "CB Employment Trends Index (Apr)"},
            {"date": soon, "event": "Retail Sales Ex Autos MoM (Apr)"},
        ]
        blocked, _ = check_macro_blackout(cal)
        assert blocked is False

    def test_mix_keeps_high_impact_winner(self):
        from titantrade.risk_manager import check_macro_blackout
        import datetime as dt
        soon = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=2)).isoformat()
        cal = [
            {"date": soon, "event": "Atlanta Fed GDPNow (Q2)"},
            {"date": soon, "event": "FOMC Minutes"},  # high-impact
        ]
        blocked, name = check_macro_blackout(cal)
        assert blocked is True
        assert "FOMC" in name

    def test_event_beyond_window_does_not_block(self):
        from titantrade.risk_manager import check_macro_blackout
        import datetime as dt
        far = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=48)).isoformat()
        cal = [{"date": far, "event": "FOMC Minutes"}]
        blocked, _ = check_macro_blackout(cal)
        assert blocked is False


# ---------------------------------------------------------------------------
# adjusted_confidence wiring (#3)
# ---------------------------------------------------------------------------

class TestAdjustedConfidenceUsed:
    @pytest.fixture(autouse=True)
    def _mock_sector(self, monkeypatch):
        monkeypatch.setattr(
            "titantrade.risk_manager.get_stock_sector", lambda t: "Technology",
        )

    def test_pre_trade_check_uses_adjusted_confidence(
        self, tmp_state_dir, fake_config, bullish_thesis, sample_positions,
    ):
        """When adjusted_confidence is set (by Pass 2), it overrides the
        original confidence for the gate AND for confidence-scaled sizing."""
        # Pass-1 confidence 0.72, Pass-2 raised to 0.95 → larger position
        thesis_low_high = dict(bullish_thesis)
        thesis_low_high["confidence"] = 0.72
        thesis_low_high["adjusted_confidence"] = 0.95

        result_high = pre_trade_check(
            ticker="AAPL", thesis=thesis_low_high,
            portfolio_value=100_000, cash_balance=50_000,
            positions=sample_positions, stock_atr=3.0,
            earnings_blocked=False, cfg=fake_config,
        )
        assert result_high["allowed"] is True

        # Compare against same thesis with no adjustment (uses 0.72)
        thesis_no_adj = dict(bullish_thesis)
        thesis_no_adj["confidence"] = 0.72
        thesis_no_adj.pop("adjusted_confidence", None)
        result_low = pre_trade_check(
            ticker="AAPL", thesis=thesis_no_adj,
            portfolio_value=100_000, cash_balance=50_000,
            positions=sample_positions, stock_atr=3.0,
            earnings_blocked=False, cfg=fake_config,
        )
        assert result_low["allowed"] is True
        # Higher adjusted confidence → more shares
        assert result_high["shares"] > result_low["shares"]

    def test_fallback_to_original_when_no_adjustment(
        self, tmp_state_dir, fake_config, bullish_thesis, sample_positions,
    ):
        """When adjusted_confidence is absent, original confidence is used."""
        # No adjusted_confidence in fixture
        result = pre_trade_check(
            ticker="AAPL", thesis=bullish_thesis,
            portfolio_value=100_000, cash_balance=50_000,
            positions=sample_positions, stock_atr=3.0,
            earnings_blocked=False, cfg=fake_config,
        )
        assert result["allowed"] is True


# ---------------------------------------------------------------------------
# Min-notional dust guard (production: URI 0.01 sh = $11, ANET 0.19 sh = $35)
# ---------------------------------------------------------------------------

class TestMinNotionalGate:
    @pytest.fixture(autouse=True)
    def _mock_sector(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(
            "titantrade.risk_manager.get_stock_sector", lambda t: "Technology"
        )

    def test_dust_order_blocked(
        self, tmp_state_dir, fake_config, bullish_thesis, sample_positions,
    ):
        # Cash reserve leaves only $300 investable → sizing shrinks to 1 share
        # of a $185.50 stock = $185.50 notional < $500 floor → blocked.
        result = pre_trade_check(
            ticker="AAPL", thesis=bullish_thesis,
            portfolio_value=100_000, cash_balance=5_300,
            positions=sample_positions, stock_atr=3.0,
            earnings_blocked=False, cfg=fake_config,
        )
        assert result["allowed"] is False
        assert "position_size" in result["failed_gates"]
        assert "minimum notional" in result["gate_results"]["position_size"]["detail"]
        assert result["shares"] == 0

    def test_sub_share_dust_blocked(
        self, tmp_state_dir, fake_config, bullish_thesis, sample_positions,
    ):
        # The production shape: a high-priced stock and almost no free cash
        # produce a fractional sliver (0.16 sh of a $1,106 stock ≈ $177).
        thesis = dict(bullish_thesis)
        thesis["target_entry_price"] = 1_106.15
        result = pre_trade_check(
            ticker="AAPL", thesis=thesis,
            portfolio_value=100_000, cash_balance=5_180,
            positions=sample_positions, stock_atr=3.0,
            earnings_blocked=False, cfg=fake_config,
        )
        assert result["allowed"] is False
        assert "position_size" in result["failed_gates"]
        assert "minimum notional" in result["gate_results"]["position_size"]["detail"]

    def test_position_at_floor_passes(
        self, tmp_state_dir, fake_config, bullish_thesis, sample_positions,
    ):
        # $800 investable → 4 shares × $185.50 = $742 ≥ $500 → passes.
        result = pre_trade_check(
            ticker="AAPL", thesis=bullish_thesis,
            portfolio_value=100_000, cash_balance=5_800,
            positions=sample_positions, stock_atr=3.0,
            earnings_blocked=False, cfg=fake_config,
        )
        assert result["allowed"] is True
        assert result["shares"] == 4.0

    def test_normal_sizing_unaffected(
        self, tmp_state_dir, fake_config, bullish_thesis, sample_positions,
    ):
        # Plenty of cash: the floor must not change ordinary sizing.
        result = pre_trade_check(
            ticker="AAPL", thesis=bullish_thesis,
            portfolio_value=100_000, cash_balance=50_000,
            positions=sample_positions, stock_atr=3.0,
            earnings_blocked=False, cfg=fake_config,
        )
        assert result["allowed"] is True
        assert result["shares"] * bullish_thesis["target_entry_price"] >= 500


# ---------------------------------------------------------------------------
# Suspect portfolio-value guard (production: Alpaca returned $22,828 against
# a real ~$100k equity mid-way through CRWD split processing, 2026-07-07)
# ---------------------------------------------------------------------------

class TestSuspectPortfolioValue:
    def test_phantom_drawdown_blocks_but_preserves_peak(self, tmp_state_dir: Path):
        # The Jul 7 numbers: peak $109,131.75, reported value $22,828.05.
        write_state_file(
            tmp_state_dir, "peak_portfolio.json", {"peak_value": 109_131.75}
        )
        tripped, pct = check_drawdown_circuit_breaker(22_828.05)
        # Entries stay blocked (fail-safe) …
        assert tripped is True
        assert pct > 50
        # … and the peak file is untouched.
        from titantrade.risk_manager import load_peak_value
        assert load_peak_value() == 109_131.75

    def test_absurd_spike_not_recorded_as_peak(self, tmp_state_dir: Path):
        # The inverse glitch: a 5x "gain" must not corrupt the peak file —
        # that would permanently trip the breaker once real values return.
        write_state_file(
            tmp_state_dir, "peak_portfolio.json", {"peak_value": 100_000}
        )
        from titantrade.risk_manager import load_peak_value, update_peak_value
        assert update_peak_value(500_000) == 100_000
        assert load_peak_value() == 100_000
        # And the breaker must not report a nonsense negative drawdown.
        tripped, pct = check_drawdown_circuit_breaker(500_000)
        assert tripped is False
        assert pct == 0.0

    def test_moderate_new_high_still_updates_peak(self, tmp_state_dir: Path):
        # +40% is within the plausibility band — normal peak tracking.
        write_state_file(
            tmp_state_dir, "peak_portfolio.json", {"peak_value": 100_000}
        )
        from titantrade.risk_manager import load_peak_value, update_peak_value
        assert update_peak_value(140_000) == 140_000
        assert load_peak_value() == 140_000

    def test_real_drawdown_still_trips_normally(self, tmp_state_dir: Path):
        # A genuine 20% drawdown is NOT suspect — trips with the real number.
        write_state_file(
            tmp_state_dir, "peak_portfolio.json", {"peak_value": 100_000}
        )
        tripped, pct = check_drawdown_circuit_breaker(80_000)
        assert tripped is True
        assert pct == 20.0

    def test_suspect_wording_in_pre_trade_check(
        self, tmp_state_dir, fake_config, bullish_thesis, sample_positions,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr(
            "titantrade.risk_manager.get_stock_sector", lambda t: "Technology"
        )
        write_state_file(
            tmp_state_dir, "peak_portfolio.json", {"peak_value": 109_131.75}
        )
        result = pre_trade_check(
            ticker="AAPL", thesis=bullish_thesis,
            portfolio_value=22_828.05, cash_balance=10_000,
            positions=sample_positions, stock_atr=3.0,
            earnings_blocked=False, cfg=fake_config,
        )
        assert result["allowed"] is False
        assert "drawdown" in result["failed_gates"]
        detail = result["gate_results"]["drawdown"]["detail"]
        assert "suspect broker data" in detail
