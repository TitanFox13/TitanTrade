"""Tests for daily sentry (Gemini integration) with MOCKED AI calls.

CRITICAL: _call_gemini, _fetch_current_price, and _fetch_spy_quote are
always monkeypatched. No real API calls. Zero tokens spent.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from titantrade.daily_sentry import check_stock


CONTINUE_JSON = json.dumps({
    "ticker": "AAPL",
    "signal": "CONTINUE",
    "conflicting_headlines": [],
    "price_concern": False,
    "market_concern": False,
    "reasoning": "No material news contradicts thesis",
})

ABORT_JSON = json.dumps({
    "ticker": "AAPL",
    "signal": "ABORT",
    "conflicting_headlines": ["Apple CEO resigns unexpectedly"],
    "price_concern": False,
    "market_concern": False,
    "reasoning": "CEO departure matches thesis breach condition",
})


@pytest.fixture
def thesis():
    return {
        "ticker": "AAPL",
        "thesis": "BULLISH",
        "confidence": 0.78,
        "target_entry_price": 185.50,
        "thesis_breach_condition": "CEO departure",
        "reasoning": "Strong iPhone cycle",
    }


@pytest.fixture
def price_check_ok():
    return {"adverse_move": False, "move_pct": 0.5, "current_price": 186.0, "alert": "Within range"}


@pytest.fixture
def price_check_adverse():
    return {"adverse_move": True, "move_pct": -4.2, "current_price": 177.7, "alert": "ADVERSE"}


@pytest.fixture
def market_check_ok():
    return {"market_stress": False, "spy_change_pct": 0.3, "alert": "OK"}


class TestCheckStock:
    def test_continue_signal(self, fake_config, thesis, price_check_ok, market_check_ok):
        with patch("titantrade.daily_sentry._call_gemini", return_value=CONTINUE_JSON):
            result = check_stock("AAPL", thesis, [], price_check_ok, market_check_ok, fake_config)
        assert result["signal"] == "CONTINUE"

    def test_abort_signal(self, fake_config, thesis, price_check_ok, market_check_ok):
        with patch("titantrade.daily_sentry._call_gemini", return_value=ABORT_JSON):
            result = check_stock("AAPL", thesis, [], price_check_ok, market_check_ok, fake_config)
        assert result["signal"] == "ABORT"
        assert len(result["conflicting_headlines"]) > 0

    def test_price_override_forces_abort(self, fake_config, thesis, price_check_adverse, market_check_ok):
        """Even if Gemini says CONTINUE, adverse price move forces ABORT."""
        with patch("titantrade.daily_sentry._call_gemini", return_value=CONTINUE_JSON):
            result = check_stock("AAPL", thesis, [], price_check_adverse, market_check_ok, fake_config)
        assert result["signal"] == "ABORT"
        assert result["price_concern"] is True

    def test_garbage_response_defaults_to_continue(self, fake_config, thesis, price_check_ok, market_check_ok):
        with patch("titantrade.daily_sentry._call_gemini", return_value="not json"):
            result = check_stock("AAPL", thesis, [], price_check_ok, market_check_ok, fake_config)
        assert result["signal"] == "CONTINUE"

    def test_garbage_with_adverse_price_still_aborts(self, fake_config, thesis, price_check_adverse, market_check_ok):
        """Parse failure + adverse price = ABORT (price override applies regardless)."""
        with patch("titantrade.daily_sentry._call_gemini", return_value="broken"):
            result = check_stock("AAPL", thesis, [], price_check_adverse, market_check_ok, fake_config)
        assert result["signal"] == "ABORT"
