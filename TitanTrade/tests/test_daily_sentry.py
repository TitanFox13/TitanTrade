"""Tests for daily sentry (Gemini integration) with MOCKED AI calls.

CRITICAL: _call_gemini, _fetch_current_price, and _fetch_spy_quote are
always monkeypatched. No real API calls. Zero tokens spent.
"""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

from titantrade.daily_sentry import check_stock, _call_gemini


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
    """Moderate adverse move: 3-5% — should NOT auto-ABORT unless news confirms."""
    return {"adverse_move": True, "move_pct": -4.2, "current_price": 177.7, "alert": "ADVERSE"}


@pytest.fixture
def price_check_catastrophic():
    """Catastrophic move: >5% — should ALWAYS ABORT regardless of news."""
    return {"adverse_move": True, "move_pct": -6.5, "current_price": 173.5, "alert": "CATASTROPHIC"}


@pytest.fixture
def market_check_ok():
    return {"market_stress": False, "spy_change_pct": 0.3, "alert": "OK"}


class TestCheckStock:
    def test_continue_signal(self, fake_config, thesis, price_check_ok, market_check_ok):
        with patch("titantrade.daily_sentry._call_gemini", return_value=CONTINUE_JSON):
            result = check_stock("AAPL", thesis, [], price_check_ok, market_check_ok, fake_config)
        assert result["signal"] == "CONTINUE"

    def test_abort_signal_with_price_confirmation(
        self, fake_config, thesis, price_check_adverse, market_check_ok,
    ):
        """Gemini ABORT + adverse price move = confirmed ABORT.

        Note: news-only ABORT (Gemini ABORT + price is fine) is now
        downgraded to CONTINUE — see test_news_only_abort_downgraded.
        ABORT requires BOTH news AND price confirmation.
        """
        with patch("titantrade.daily_sentry._call_gemini", return_value=ABORT_JSON):
            result = check_stock("AAPL", thesis, [], price_check_adverse, market_check_ok, fake_config)
        assert result["signal"] == "ABORT"
        assert len(result["conflicting_headlines"]) > 0

    def test_news_only_abort_downgraded(
        self, fake_config, thesis, price_check_ok, market_check_ok,
    ):
        """Strategic policy: Gemini alone cannot kill a position. If price is
        holding (or rising!) and only the news interpretation says ABORT, we
        downgrade to CONTINUE. The programmatic stop is the only kill switch
        for losers. Prevents the GS-style whipsaw round-trip we saw in prod.
        """
        with patch("titantrade.daily_sentry._call_gemini", return_value=ABORT_JSON):
            result = check_stock("AAPL", thesis, [], price_check_ok, market_check_ok, fake_config)
        assert result["signal"] == "CONTINUE"
        assert "downgraded" in result["reasoning"].lower()

    def test_position_context_included_in_prompt(
        self, fake_config, thesis, price_check_ok, market_check_ok,
    ):
        """The sentry prompt now includes position context (entry, current,
        unrealized P&L) so Gemini's call is grounded in trade economics."""
        captured_prompt = {}

        def _capture(prompt, cfg, cost_label=""):
            captured_prompt["text"] = prompt
            return CONTINUE_JSON

        position = {
            "qty": "50", "avg_entry_price": "185.50",
            "current_price": "190.00", "unrealized_plpc": "0.024",
            "market_value": "9500",
        }
        with patch("titantrade.daily_sentry._call_gemini", side_effect=_capture):
            check_stock(
                "AAPL", thesis, [], price_check_ok, market_check_ok, fake_config,
                position=position,
            )

        assert "POSITION CONTEXT" in captured_prompt["text"]
        assert "$185.50" in captured_prompt["text"]
        assert "+2.4%" in captured_prompt["text"]
        # Prompt also instructs Gemini about the breach-only policy
        assert "DOWNGRADED" in captured_prompt["text"]

    def test_no_position_renders_no_position_string(
        self, fake_config, thesis, price_check_ok, market_check_ok,
    ):
        """When called with position=None, prompt should say so explicitly
        (not blank or 'unknown')."""
        captured = {}
        def _capture(prompt, cfg, cost_label=""):
            captured["text"] = prompt
            return CONTINUE_JSON

        with patch("titantrade.daily_sentry._call_gemini", side_effect=_capture):
            check_stock("AAPL", thesis, [], price_check_ok, market_check_ok, fake_config)

        assert "no open position" in captured["text"]

    def test_moderate_price_move_without_news_does_NOT_abort(
        self, fake_config, thesis, price_check_adverse, market_check_ok,
    ):
        """A 3-5% adverse move with no Gemini news concerns is treated as
        likely noise — broker-side stop will catch a real breakdown.
        This is the production fix for excessive ABORT churn.
        """
        with patch("titantrade.daily_sentry._call_gemini", return_value=CONTINUE_JSON):
            result = check_stock("AAPL", thesis, [], price_check_adverse, market_check_ok, fake_config)
        assert result["signal"] == "CONTINUE"
        # We still flag the concern in the signal payload for visibility
        assert result["price_concern"] is True
        assert "no news corroboration" in result["reasoning"].lower()

    def test_moderate_price_move_WITH_news_concerns_aborts(
        self, fake_config, thesis, price_check_adverse, market_check_ok,
    ):
        """3-5% adverse + Gemini found conflicting headlines = confirmed ABORT."""
        with patch("titantrade.daily_sentry._call_gemini", return_value=ABORT_JSON):
            result = check_stock("AAPL", thesis, [], price_check_adverse, market_check_ok, fake_config)
        # Gemini already returned ABORT; doesn't matter whether the override
        # also fires.
        assert result["signal"] == "ABORT"

    def test_moderate_price_with_continue_but_headlines_aborts(
        self, fake_config, thesis, price_check_adverse, market_check_ok,
    ):
        """Edge case: Gemini returns CONTINUE but flagged headlines —
        the price-move override should still confirm ABORT."""
        custom = json.dumps({
            "ticker": "AAPL",
            "signal": "CONTINUE",
            "conflicting_headlines": ["Apple recalls iPhone 16"],
            "price_concern": False,
            "market_concern": False,
            "reasoning": "Concerning but not decisive",
        })
        with patch("titantrade.daily_sentry._call_gemini", return_value=custom):
            result = check_stock("AAPL", thesis, [], price_check_adverse, market_check_ok, fake_config)
        assert result["signal"] == "ABORT"
        assert "confirmed by Gemini news" in result["reasoning"].lower() or "confirmed by gemini" in result["reasoning"].lower()

    def test_catastrophic_price_move_always_aborts(
        self, fake_config, thesis, price_check_catastrophic, market_check_ok,
    ):
        """A >5% adverse move is catastrophic and ABORTs regardless of news."""
        with patch("titantrade.daily_sentry._call_gemini", return_value=CONTINUE_JSON):
            result = check_stock("AAPL", thesis, [], price_check_catastrophic, market_check_ok, fake_config)
        assert result["signal"] == "ABORT"
        assert "hard abort" in result["reasoning"].lower()

    def test_garbage_response_defaults_to_continue(self, fake_config, thesis, price_check_ok, market_check_ok):
        with patch("titantrade.daily_sentry._call_gemini", return_value="not json"):
            result = check_stock("AAPL", thesis, [], price_check_ok, market_check_ok, fake_config)
        assert result["signal"] == "CONTINUE"

    def test_garbage_with_catastrophic_price_still_aborts(
        self, fake_config, thesis, price_check_catastrophic, market_check_ok,
    ):
        """Parse failure + catastrophic move = ABORT (hard threshold ignores news)."""
        with patch("titantrade.daily_sentry._call_gemini", return_value="broken"):
            result = check_stock("AAPL", thesis, [], price_check_catastrophic, market_check_ok, fake_config)
        assert result["signal"] == "ABORT"


# ---------------------------------------------------------------------------
# Price-move uses avg_entry_price when position present (#6)
# ---------------------------------------------------------------------------

class TestPriceMovePositionAware:
    @patch("titantrade.daily_sentry._fetch_current_price", return_value=200.0)
    def test_held_position_uses_avg_entry(self, mock_price, fake_config):
        """For a held position, _check_price_move should reference
        position.avg_entry_price, not thesis.target_entry_price.
        """
        from titantrade.daily_sentry import _check_price_move
        thesis = {
            "thesis": "BULLISH",
            "target_entry_price": 100.0,  # stale thesis target
        }
        position = {"avg_entry_price": "180.0", "qty": "10"}
        # Current $200, entry $180 → +11% (not adverse). If we used the stale
        # thesis target $100 it would look like +100% (no adverse).
        result = _check_price_move("AAPL", thesis, fake_config, position=position)
        assert result["adverse_move"] is False
        # The move was computed off $180 (broker entry), not $100 (thesis)
        assert abs(result["move_pct"] - 11.11) < 0.1

    @patch("titantrade.daily_sentry._fetch_current_price", return_value=170.0)
    def test_held_position_detects_real_drawdown(self, mock_price, fake_config):
        """Drop below avg_entry_price by >3% triggers adverse_move."""
        from titantrade.daily_sentry import _check_price_move
        thesis = {"thesis": "BULLISH", "target_entry_price": 100.0}
        position = {"avg_entry_price": "180.0", "qty": "10"}
        # Current $170, entry $180 → -5.5% (adverse). Without position-aware
        # reference, current vs thesis target $100 = +70% (would miss the drawdown).
        result = _check_price_move("AAPL", thesis, fake_config, position=position)
        assert result["adverse_move"] is True
        assert result["move_pct"] < -3.0

    @patch("titantrade.daily_sentry._fetch_current_price", return_value=170.0)
    def test_no_position_falls_back_to_thesis_target(self, mock_price, fake_config):
        from titantrade.daily_sentry import _check_price_move
        thesis = {"thesis": "BULLISH", "target_entry_price": 180.0}
        # No position passed in
        result = _check_price_move("AAPL", thesis, fake_config)
        assert result["adverse_move"] is True  # -5.5% from 180


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

    @patch("titantrade.daily_sentry.notify_sentry_degraded")
    @patch("titantrade.daily_sentry.fetch_news", return_value=[])
    @patch("titantrade.daily_sentry._fetch_current_price", return_value=100.0)
    @patch("titantrade.daily_sentry._fetch_spy_quote", return_value=0.3)
    @patch("titantrade.daily_sentry._call_gemini")
    def test_fallback_emits_explicit_signal_log_line(
        self, mock_gemini, mock_spy, mock_price, mock_news, mock_notify,
        fake_config, tmp_state_dir, caplog,
    ):
        """Regression check: when Gemini retries are exhausted, the resulting
        fallback signal must be logged with the same [sentry] TICKER: SIGNAL
        shape as the happy path. Previously only the ERROR line appeared,
        leaving operators to guess at what the sentry decided.
        """
        fake_config.trading.watchlist.clear()
        fake_config.trading.watchlist.extend(["AAPL"])

        mock_gemini.side_effect = RuntimeError("All 5 attempts failed: 503")

        thesis_doc = _thesis_doc([_full_thesis("AAPL")])
        write_state_file(tmp_state_dir, "weekly_thesis.json", thesis_doc)

        import logging
        with caplog.at_level(logging.WARNING, logger="titantrade.sentry"):
            run_daily_sentry(fake_config)

        fallback_log_lines = [
            r.message for r in caplog.records
            if r.message.startswith("[sentry] AAPL:")
            and "fallback" in r.message.lower()
        ]
        assert len(fallback_log_lines) == 1, (
            f"Expected one explicit fallback log line, got: {fallback_log_lines}"
        )
        # The fallback was CONTINUE (no adverse price move in the fixture)
        assert "CONTINUE" in fallback_log_lines[0]


# ---------------------------------------------------------------------------
# Gemini model-fallback chain (503 "model overloaded" resilience)
# ---------------------------------------------------------------------------

def _gemini_ok(text: str = '{"signal":"CONTINUE"}'):
    m = MagicMock()
    m.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": text}]}}],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
    }
    return m


class TestGeminiModelFallback:
    """On a persistent 503 on the primary model, _call_gemini falls back to
    the next configured model (a separate capacity pool) before giving up."""

    def test_falls_back_to_next_model_on_failure(self, fake_config):
        # Primary raises (simulating exhausted 503 retries), fallback succeeds.
        calls = []

        def _side(method, url, **kwargs):
            calls.append(url)
            if len(calls) == 1:
                raise RuntimeError("503 model overloaded")
            return _gemini_ok()

        with patch("titantrade.daily_sentry.fetch_with_retry", side_effect=_side):
            out = _call_gemini("prompt", fake_config)

        assert out == '{"signal":"CONTINUE"}'
        assert len(calls) == 2                      # primary + 1 fallback
        assert fake_config.gemini.model in calls[0]  # tried primary first
        assert fake_config.gemini.fallback_models[0] in calls[1]  # then fallback

    def test_raises_when_all_models_fail(self, fake_config):
        with patch(
            "titantrade.daily_sentry.fetch_with_retry",
            side_effect=RuntimeError("503 model overloaded"),
        ) as m:
            with pytest.raises(RuntimeError):
                _call_gemini("prompt", fake_config)
        # primary + all fallbacks attempted
        assert m.call_count == 1 + len(fake_config.gemini.fallback_models)

    def test_primary_success_no_fallback(self, fake_config):
        with patch(
            "titantrade.daily_sentry.fetch_with_retry", return_value=_gemini_ok(),
        ) as m:
            _call_gemini("prompt", fake_config)
        assert m.call_count == 1  # primary answered, no fallback needed
