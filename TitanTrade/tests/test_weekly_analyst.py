"""Tests for weekly analyst (Claude integration) with MOCKED AI calls.

CRITICAL: _call_claude is always monkeypatched. No real API calls are made.
Zero tokens are spent running these tests.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from titantrade.weekly_analyst import analyze_stock, rank_and_select


VALID_THESIS_JSON = json.dumps({
    "ticker": "AAPL",
    "thesis": "BULLISH",
    "confidence": 0.78,
    "target_entry_price": 185.50,
    "stop_loss_price": 176.23,
    "take_profit_price": 198.00,
    "thesis_breach_condition": "CEO departure",
    "reasoning": "Strong iPhone cycle and services growth",
})

VALID_RANKING_JSON = json.dumps({
    "selected_tickers": ["AAPL", "LLY"],
    "market_regime_assessment": "Bullish with normal volatility",
    "selections": [
        {"ticker": "AAPL", "original_confidence": 0.78, "adjusted_confidence": 0.75, "reason_selected": "Strong setup"},
        {"ticker": "LLY", "original_confidence": 0.82, "adjusted_confidence": 0.80, "reason_selected": "Healthcare diversification"},
    ],
    "rejections": [
        {"ticker": "TSLA", "reason_rejected": "Too volatile in current regime"},
    ],
})


class TestAnalyzeStock:
    def test_valid_response(self, fake_config):
        with patch("titantrade.weekly_analyst._call_claude", return_value=VALID_THESIS_JSON):
            result = analyze_stock(
                ticker="AAPL",
                stock_data={"ohlcv_recent": [], "technical_indicators": {}, "news": [], "sec_filings": [], "earnings": {}},
                market_ctx={"market_regime": "bullish"},
                performance_text="",
                cfg=fake_config,
            )
        assert result["ticker"] == "AAPL"
        assert result["thesis"] == "BULLISH"
        assert result["confidence"] == 0.78

    def test_garbage_response_falls_back_to_neutral(self, fake_config):
        with patch("titantrade.weekly_analyst._call_claude", return_value="This is not JSON at all"):
            result = analyze_stock(
                ticker="AAPL",
                stock_data={},
                market_ctx={},
                performance_text="",
                cfg=fake_config,
            )
        assert result["ticker"] == "AAPL"
        assert result["thesis"] == "NEUTRAL"

    def test_partial_json_fills_defaults(self, fake_config):
        partial = json.dumps({"ticker": "AAPL", "thesis": "BEARISH"})
        with patch("titantrade.weekly_analyst._call_claude", return_value=partial):
            result = analyze_stock(
                ticker="AAPL",
                stock_data={},
                market_ctx={},
                performance_text="",
                cfg=fake_config,
            )
        assert result["thesis"] == "BEARISH"
        assert result["confidence"] == 0.5  # default


class TestRankAndSelect:
    def test_valid_ranking(self, fake_config):
        theses = [
            {"ticker": "AAPL", "thesis": "BULLISH", "confidence": 0.78},
            {"ticker": "LLY", "thesis": "BULLISH", "confidence": 0.82},
            {"ticker": "TSLA", "thesis": "BULLISH", "confidence": 0.65},
        ]
        with patch("titantrade.weekly_analyst._call_claude", return_value=VALID_RANKING_JSON):
            result = rank_and_select(
                all_theses=theses,
                market_ctx={},
                holdings=[],
                sector_exposure={},
                performance_text="",
                cfg=fake_config,
            )
        assert "AAPL" in result["selected_tickers"]
        assert "LLY" in result["selected_tickers"]

    def test_garbage_falls_back_to_all_bullish(self, fake_config):
        theses = [
            {"ticker": "AAPL", "thesis": "BULLISH"},
            {"ticker": "NVDA", "thesis": "NEUTRAL"},
        ]
        with patch("titantrade.weekly_analyst._call_claude", return_value="broken"):
            result = rank_and_select(
                all_theses=theses,
                market_ctx={},
                holdings=[],
                sector_exposure={},
                performance_text="",
                cfg=fake_config,
            )
        assert "AAPL" in result["selected_tickers"]
        assert "NVDA" not in result["selected_tickers"]


# ---------------------------------------------------------------------------
# Pass 2 target count scales with regime (#5)
# ---------------------------------------------------------------------------

class TestPass2TargetCount:
    def test_strong_bullish_targets_more(self):
        from titantrade.weekly_analyst import _target_pass2_count
        assert _target_pass2_count("strong_bullish") >= 6
        assert _target_pass2_count("bullish") >= 5
        assert _target_pass2_count("neutral") == 4

    def test_bearish_targets_fewer(self):
        from titantrade.weekly_analyst import _target_pass2_count
        assert _target_pass2_count("bearish") <= 3
        assert _target_pass2_count("strong_bearish") <= 2
        assert _target_pass2_count("crisis") <= 1

    def test_unknown_regime_defaults_to_neutral(self):
        from titantrade.weekly_analyst import _target_pass2_count
        assert _target_pass2_count("weird") == _target_pass2_count("neutral")


# ---------------------------------------------------------------------------
# Earnings blackout narrowed window (#7)
# ---------------------------------------------------------------------------

class TestEarningsBlackoutNarrowed:
    def test_default_window_is_2_days(self):
        from titantrade.earnings import DEFAULT_BLOCK_DAYS
        assert DEFAULT_BLOCK_DAYS == 2

    def test_4_days_out_no_longer_blocks(self):
        """A position with earnings 4 days out should NOT be blocked under
        the new 2-day window (was blocked under the old 5-day rule).
        We use 4 days rather than 3 because ``(earnings_dt - now).days``
        rounds down — 3 calendar days at noon may register as 2.
        """
        import datetime as dt
        from titantrade.earnings import is_earnings_blocked
        earnings_date = (dt.date.today() + dt.timedelta(days=4)).isoformat()
        blocked, _ = is_earnings_blocked("AAPL", earnings_date)
        assert blocked is False

    def test_1_day_out_still_blocks(self):
        import datetime as dt
        from titantrade.earnings import is_earnings_blocked
        earnings_date = (dt.date.today() + dt.timedelta(days=1)).isoformat()
        blocked, _ = is_earnings_blocked("AAPL", earnings_date)
        assert blocked is True
