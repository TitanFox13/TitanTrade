"""ATR (the live strategy's only indicator besides the SMA in signals.py)."""

from titantrade.indicators import atr


def _bars(closes, rng=1.0):
    return [{"open": c, "high": c + rng, "low": c - rng, "close": c, "volume": 1} for c in closes]


class TestATR:
    def test_insufficient_data(self):
        assert atr(_bars([100.0] * 10)) is None

    def test_constant_range(self):
        assert atr(_bars([100.0] * 30, rng=1.0)) == 2.0
        assert atr(_bars([100.0] * 30, rng=1.0), period=5) == 2.0

    def test_gap_counts_in_true_range(self):
        bars = _bars([100.0] * 20, rng=0.5) + _bars([110.0] * 20, rng=0.5)
        assert atr(bars) > 1.0


class TestCorrelation:
    def test_perfect_inverse_and_short(self):
        import pytest
        from titantrade.indicators import correlation
        a = [100.0 + i + 3 * (i % 4) for i in range(70)]       # trending, non-constant returns
        b = [1000.0 - x for x in a]
        assert correlation(a, a) == pytest.approx(1.0)
        assert correlation(a, b) <= -0.99
        assert correlation(a[:10], a[:10]) is None
        assert correlation([100.0] * 70, a) is None            # zero variance
