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


# ---------------------------------------------------------------------------
# run_daily_sentry — skip non-selected tickers + fallback observability
# ---------------------------------------------------------------------------

from titantrade.daily_sentry import run_daily_sentry
from tests.conftest import write_state_file


def _thesis_doc(entries: list[dict]) -> dict:
    return {
        "generated_at": "2026-04-18T00:00:00+00:00",
        "next_review_at": "2026-04-25T00:00:00+00:00",
        "market_regime": "bullish",
        "theses": entries,
    }


def _full_thesis(ticker: str, **overrides):
    base = {
        "ticker": ticker,
        "thesis": "BULLISH",
        "confidence": 0.80,
        "target_entry_price": 100.0,
        "thesis_breach_condition": "breach",
        "reasoning": "rationale",
        "selected_for_trading": True,
    }
    base.update(overrides)
    return base


class TestNonSelectedSkip:
    @patch("titantrade.daily_sentry._call_gemini", return_value=CONTINUE_JSON)
    @patch("titantrade.daily_sentry.fetch_news", return_value=[])
    @patch("titantrade.daily_sentry._fetch_current_price", return_value=100.0)
    @patch("titantrade.daily_sentry._fetch_spy_quote", return_value=0.3)
    def test_skips_when_not_selected(
        self, mock_spy, mock_price, mock_news, mock_gemini,
        fake_config, tmp_state_dir,
    ):
        """Positions closed by the weekly review have selected_for_trading=False
        and must be skipped by the sentry — no Gemini call, no ghost ABORT."""
        # Limit the watchlist so the rest of the test doesn't iterate 15 tickers.
        fake_config.trading.watchlist.clear()
        fake_config.trading.watchlist.extend(["AAPL", "DXCM"])

        thesis_doc = _thesis_doc([
            _full_thesis("AAPL", selected_for_trading=True),
            # DXCM: Claude said CLOSE in the weekly review, position already gone.
            _full_thesis("DXCM", selected_for_trading=False, review_action="CLOSE"),
        ])
        write_state_file(tmp_state_dir, "weekly_thesis.json", thesis_doc)

        result = run_daily_sentry(fake_config)

        signals_by_ticker = {s["ticker"]: s for s in result["signals"]}
        assert signals_by_ticker["DXCM"]["signal"] == "CONTINUE"
        assert "skipped" in signals_by_ticker["DXCM"]["reasoning"].lower()

        # AAPL went through the real Gemini path, DXCM did not.
        # _call_gemini is called once per sentry check. We skipped DXCM via the
        # selected_for_trading gate BEFORE invoking Gemini, so exactly one call
        # should have been made (for AAPL).
        assert mock_gemini.call_count == 1


class TestSentryObservability:
    @patch("titantrade.daily_sentry.notify_sentry_degraded")
    @patch("titantrade.daily_sentry.fetch_news", return_value=[])
    @patch("titantrade.daily_sentry._fetch_current_price", return_value=100.0)
    @patch("titantrade.daily_sentry._fetch_spy_quote", return_value=0.3)
    @patch("titantrade.daily_sentry._call_gemini")
    def test_alerts_when_fallback_ratio_above_30pct(
        self, mock_gemini, mock_spy, mock_price, mock_news, mock_notify,
        fake_config, tmp_state_dir,
    ):
        """Simulate 3/4 Gemini calls failing → fallback ratio 75% → Discord alert fires."""
        fake_config.trading.watchlist.clear()
        fake_config.trading.watchlist.extend(["AAPL", "NVDA", "TSLA", "MSFT"])

        # First 3 calls raise, last one succeeds
        mock_gemini.side_effect = [
            RuntimeError("Gemini 503"),
            RuntimeError("Gemini 503"),
            RuntimeError("Gemini 503"),
            CONTINUE_JSON,
        ]

        thesis_doc = _thesis_doc([
            _full_thesis(t) for t in ("AAPL", "NVDA", "TSLA", "MSFT")
        ])
        write_state_file(tmp_state_dir, "weekly_thesis.json", thesis_doc)

        result = run_daily_sentry(fake_config)

        assert result["failures"]["fallback_count"] == 3
        assert result["failures"]["checks_run"] == 4
        assert result["failures"]["fallback_ratio"] == 0.75
        mock_notify.assert_called_once()

    @patch("titantrade.daily_sentry.notify_sentry_degraded")
    @patch("titantrade.daily_sentry.fetch_news", return_value=[])
    @patch("titantrade.daily_sentry._fetch_current_price", return_value=100.0)
    @patch("titantrade.daily_sentry._fetch_spy_quote", return_value=0.3)
    @patch("titantrade.daily_sentry._call_gemini", return_value=CONTINUE_JSON)
    def test_no_alert_when_all_succeed(
        self, mock_gemini, mock_spy, mock_price, mock_news, mock_notify,
        fake_config, tmp_state_dir,
    ):
        fake_config.trading.watchlist.clear()
        fake_config.trading.watchlist.extend(["AAPL", "NVDA"])

        thesis_doc = _thesis_doc([_full_thesis(t) for t in ("AAPL", "NVDA")])
        write_state_file(tmp_state_dir, "weekly_thesis.json", thesis_doc)

        result = run_daily_sentry(fake_config)

        assert result["failures"]["fallback_count"] == 0
        mock_notify.assert_not_called()
