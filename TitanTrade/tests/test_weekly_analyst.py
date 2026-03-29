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
