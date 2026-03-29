"""Tests for technical indicator computations.

All functions are pure math — no I/O, no API calls, no AI tokens spent.
"""

from titantrade.indicators import (
    atr,
    bollinger_bands,
    compute_all_indicators,
    ema,
    ema_series,
    macd,
    price_vs_sma,
    rsi,
    sma,
    sma_series,
    volume_trend,
)


# ---------------------------------------------------------------------------
# SMA
# ---------------------------------------------------------------------------

class TestSMA:
    def test_basic(self):
        assert sma([1, 2, 3, 4, 5], 3) == 4.0  # (3+4+5)/3

    def test_full_period(self):
        assert sma([10, 20, 30], 3) == 20.0

    def test_insufficient_data(self):
        assert sma([1, 2], 3) is None

    def test_single_value(self):
        assert sma([5.0], 1) == 5.0


class TestSMASeries:
    def test_length_matches_input(self):
        values = [1, 2, 3, 4, 5]
        result = sma_series(values, 3)
        assert len(result) == len(values)

    def test_first_entries_are_none(self):
        result = sma_series([1, 2, 3, 4, 5], 3)
        assert result[0] is None
        assert result[1] is None
        assert result[2] is not None

    def test_values_correct(self):
        result = sma_series([1, 2, 3, 4, 5], 3)
        assert result[2] == 2.0  # (1+2+3)/3
        assert result[3] == 3.0  # (2+3+4)/3
        assert result[4] == 4.0  # (3+4+5)/3


# ---------------------------------------------------------------------------
# EMA
# ---------------------------------------------------------------------------

class TestEMA:
    def test_insufficient_data(self):
        assert ema([1, 2], 5) is None

    def test_single_period(self):
        result = ema([10, 20, 30], 1)
        # EMA(1) = last value (multiplier k=1)
        assert result == 30.0

    def test_seed_is_sma(self):
        values = [22, 22, 22, 22, 22]
        result = ema(values, 5)
        assert result == 22.0  # Constant series -> EMA = value

    def test_series_length(self):
        values = list(range(20))
        result = ema_series(values, 10)
        # Length = len(values) - period + 1
        assert len(result) == 11


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------

class TestRSI:
    def test_insufficient_data(self):
        assert rsi([1, 2, 3], 14) is None

    def test_constant_price_returns_100(self):
        # No losses -> RSI = 100
        values = [100.0] * 20
        result = rsi(values, 14)
        assert result == 100.0

    def test_strictly_increasing(self):
        values = list(range(1, 25))  # 1..24, all gains
        result = rsi(values, 14)
        assert result == 100.0

    def test_strictly_decreasing(self):
        values = list(range(24, 0, -1))  # 24..1, all losses
        result = rsi(values, 14)
        assert result is not None
        assert result < 1.0  # Very close to 0

    def test_midrange(self, sample_bars):
        """With oscillating data, RSI should be in a reasonable range."""
        closes = [b["close"] for b in sample_bars]
        result = rsi(closes, 14)
        assert result is not None
        assert 20 < result < 80


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------

class TestMACD:
    def test_insufficient_data(self):
        result = macd([1, 2, 3])
        assert result["macd_line"] is None
        assert result["signal_line"] is None
        assert result["histogram"] is None

    def test_with_enough_data(self, sample_bars):
        closes = [b["close"] for b in sample_bars]
        result = macd(closes)
        assert result["macd_line"] is not None
        assert result["signal_line"] is not None
        assert result["histogram"] is not None

    def test_uptrend_positive_macd(self):
        # Strong uptrend -> fast EMA > slow EMA -> positive MACD
        values = [100 + i * 2 for i in range(50)]
        result = macd(values)
        assert result["macd_line"] is not None
        assert result["macd_line"] > 0


# ---------------------------------------------------------------------------
# Bollinger Bands
# ---------------------------------------------------------------------------

class TestBollingerBands:
    def test_insufficient_data(self):
        result = bollinger_bands([1, 2], 20)
        assert result["upper"] is None

    def test_constant_series(self):
        values = [50.0] * 20
        result = bollinger_bands(values, 20)
        assert result["upper"] == 50.0
        assert result["middle"] == 50.0
        assert result["lower"] == 50.0

    def test_band_ordering(self, sample_bars):
        closes = [b["close"] for b in sample_bars]
        result = bollinger_bands(closes)
        assert result["upper"] > result["middle"] > result["lower"]


# ---------------------------------------------------------------------------
# ATR
# ---------------------------------------------------------------------------

class TestATR:
    def test_insufficient_data(self):
        bars = [{"high": 10, "low": 9, "close": 9.5}] * 5
        assert atr(bars, 14) is None

    def test_constant_range(self):
        # Bars with consistent TR = 2.0 (high - low)
        bars = []
        for i in range(20):
            bars.append({"high": 12.0, "low": 10.0, "close": 11.0})
        result = atr(bars, 14)
        assert result is not None
        assert abs(result - 2.0) < 0.01

    def test_with_sample_data(self, sample_bars):
        result = atr(sample_bars, 14)
        assert result is not None
        assert result > 0


# ---------------------------------------------------------------------------
# Volume Trend
# ---------------------------------------------------------------------------

class TestVolumeTrend:
    def test_with_sample_data(self, sample_bars):
        result = volume_trend(sample_bars)
        assert result["avg_volume_5d"] is not None
        assert result["avg_volume_20d"] is not None
        assert result["volume_ratio_5d_20d"] is not None

    def test_insufficient_data(self):
        bars = [{"volume": 100}] * 3
        result = volume_trend(bars)
        assert result["avg_volume_5d"] is None


# ---------------------------------------------------------------------------
# Price vs SMA
# ---------------------------------------------------------------------------

class TestPriceVsSMA:
    def test_with_sample_data(self, sample_bars):
        result = price_vs_sma(sample_bars)
        assert result["current_price"] is not None
        assert result["sma_20"] is not None
        assert result["sma_50"] is not None
        assert result["sma_200"] is not None

    def test_uptrend_above_smas(self, sample_bars):
        result = price_vs_sma(sample_bars)
        # Sample data has gentle uptrend -> price should be above 200-SMA
        assert result["above_sma_200"] is True


# ---------------------------------------------------------------------------
# Compute All Indicators (smoke test)
# ---------------------------------------------------------------------------

class TestComputeAll:
    def test_returns_all_keys(self, sample_bars):
        result = compute_all_indicators(sample_bars)
        assert "rsi_14" in result
        assert "macd" in result
        assert "bollinger" in result
        assert "atr_14" in result
        assert "price_vs_sma" in result
        assert "volume" in result

    def test_no_exceptions_with_minimal_data(self):
        bars = [{"open": 10, "high": 11, "low": 9, "close": 10, "volume": 100}] * 5
        result = compute_all_indicators(bars)
        # Most indicators will be None with only 5 bars, but shouldn't crash
        assert "rsi_14" in result
