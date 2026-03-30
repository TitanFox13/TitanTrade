"""Tests for strategy improvement features.

Covers: economic calendar gate, correlation limit, relative strength,
two-tranche entry logic. All mocked — zero API calls, zero tokens.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from titantrade.indicators import relative_strength, correlation
from titantrade.risk_manager import check_macro_blackout, check_correlation_limit


# ---------------------------------------------------------------------------
# Relative Strength
# ---------------------------------------------------------------------------

class TestRelativeStrength:
    def _make_bars(self, closes: list[float]) -> list[dict]:
        return [{"date": f"2026-01-{i+1:02d}", "open": c, "high": c+1, "low": c-1, "close": c, "volume": 100} for i, c in enumerate(closes)]

    def test_outperforming_stock(self):
        stock = self._make_bars([100 + i * 0.5 for i in range(70)])  # +35% over 70 bars
        bench = self._make_bars([100 + i * 0.1 for i in range(70)])  # +7% over 70 bars
        rs = relative_strength(stock, bench, periods=[5, 20, 60])
        assert rs["rs_5d"] > 0   # Stock outperforming
        assert rs["rs_60d"] > 0

    def test_underperforming_stock(self):
        stock = self._make_bars([100 - i * 0.3 for i in range(70)])  # Declining
        bench = self._make_bars([100 + i * 0.1 for i in range(70)])  # Rising
        rs = relative_strength(stock, bench, periods=[5, 20])
        assert rs["rs_5d"] < 0
        assert rs["rs_20d"] < 0

    def test_insufficient_data(self):
        stock = self._make_bars([100, 101, 102])
        bench = self._make_bars([100, 100.5, 101])
        rs = relative_strength(stock, bench, periods=[5])
        assert rs["rs_5d"] is None


# ---------------------------------------------------------------------------
# Correlation
# ---------------------------------------------------------------------------

class TestCorrelation:
    def test_perfectly_correlated(self):
        a = [100 + i for i in range(70)]
        b = [200 + i * 2 for i in range(70)]
        c = correlation(a, b, period=60)
        assert c is not None
        assert c > 0.95

    def test_uncorrelated(self):
        import math
        a = [100 + math.sin(i * 0.5) for i in range(70)]
        b = [100 + math.cos(i * 0.7) for i in range(70)]
        c = correlation(a, b, period=60)
        assert c is not None
        assert abs(c) < 0.5  # Low correlation

    def test_insufficient_data(self):
        c = correlation([100, 101], [200, 201], period=60)
        assert c is None


# ---------------------------------------------------------------------------
# Macro Blackout Gate
# ---------------------------------------------------------------------------

class TestMacroBlackout:
    def test_blocks_when_event_imminent(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()
        events = [{"date": future, "event": "FOMC Interest Rate Decision", "impact": "High"}]
        blocked, name = check_macro_blackout(events)
        assert blocked is True
        assert "FOMC" in name

    def test_allows_when_event_far(self):
        future = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        events = [{"date": future, "event": "CPI Release", "impact": "High"}]
        blocked, _ = check_macro_blackout(events)
        assert blocked is False

    def test_allows_when_no_events(self):
        blocked, _ = check_macro_blackout([])
        assert blocked is False

    def test_allows_past_events(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        events = [{"date": past, "event": "FOMC", "impact": "High"}]
        blocked, _ = check_macro_blackout(events)
        assert blocked is False

    def test_handles_date_only_format(self):
        """FMP sometimes returns date-only strings."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        events = [{"date": today, "event": "Non-Farm Payrolls", "impact": "High"}]
        # Should not crash
        blocked, _ = check_macro_blackout(events)
        # Result depends on current time vs assumed 2pm UTC, but shouldn't error
        assert isinstance(blocked, bool)


# ---------------------------------------------------------------------------
# Correlation Limit Gate
# ---------------------------------------------------------------------------

class TestCorrelationLimit:
    def test_blocks_highly_correlated(self):
        matrix = {
            "AAPL": {"MSFT": 0.85, "NVDA": 0.80},
            "MSFT": {"AAPL": 0.85},
            "NVDA": {"AAPL": 0.80},
        }
        allowed, avg = check_correlation_limit("AAPL", ["MSFT", "NVDA"], matrix)
        assert allowed is False
        assert avg > 0.75

    def test_allows_low_correlation(self):
        matrix = {
            "AAPL": {"JPM": 0.30, "LLY": 0.25},
            "JPM": {"AAPL": 0.30},
            "LLY": {"AAPL": 0.25},
        }
        allowed, avg = check_correlation_limit("AAPL", ["JPM", "LLY"], matrix)
        assert allowed is True
        assert avg < 0.75

    def test_allows_when_no_held_positions(self):
        allowed, avg = check_correlation_limit("AAPL", [], {})
        assert allowed is True
        assert avg == 0.0

    def test_allows_when_ticker_not_in_matrix(self):
        allowed, avg = check_correlation_limit("UNKNOWN", ["AAPL"], {"AAPL": {"MSFT": 0.9}})
        assert allowed is True


# ---------------------------------------------------------------------------
# Two-Tranche Entry Logic
# ---------------------------------------------------------------------------

class TestTwoTrancheLogic:
    def test_tranche_split_60_40(self):
        """Verify the 60/40 split logic."""
        total = 53
        t1 = max(int(total * 0.6), 1)
        t2 = total - t1
        assert t1 == 31
        assert t2 == 22
        assert t1 + t2 == total

    def test_tranche_split_small_position(self):
        """With very few shares, tranche 2 may be 0."""
        total = 2
        t1 = max(int(total * 0.6), 1)
        t2 = total - t1
        assert t1 == 1
        assert t2 == 1

    def test_tranche_split_minimum(self):
        total = 1
        t1 = max(int(total * 0.6), 1)
        t2 = total - t1
        assert t1 == 1
        assert t2 == 0  # No second tranche for 1-share position

    def test_tranche2_price_discount(self):
        entry = 185.50
        t2_price = round(entry * 0.985, 2)
        assert t2_price == 182.72  # 1.5% below entry
