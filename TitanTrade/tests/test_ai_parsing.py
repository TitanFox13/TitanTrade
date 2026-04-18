"""Tests for AI output parsing and schema validation.

Pure string/JSON manipulation — no AI calls, no tokens spent.
"""

import pytest

from titantrade.ai_parsing import (
    extract_json,
    parse_ai_json,
    validate_ranking,
    validate_sentry_signal,
    validate_thesis,
)


# ---------------------------------------------------------------------------
# extract_json
# ---------------------------------------------------------------------------

class TestExtractJSON:
    def test_clean_json(self):
        raw = '{"ticker": "AAPL", "thesis": "BULLISH"}'
        assert extract_json(raw) == raw

    def test_markdown_fences(self):
        raw = '```json\n{"ticker": "AAPL"}\n```'
        result = extract_json(raw)
        assert '"ticker"' in result
        assert "```" not in result

    def test_extra_text_before_and_after(self):
        raw = 'Here is the analysis: {"ticker": "AAPL"} Hope this helps!'
        result = extract_json(raw)
        assert result == '{"ticker": "AAPL"}'

    def test_trailing_commas_removed(self):
        raw = '{"a": 1, "b": 2,}'
        result = extract_json(raw)
        assert result == '{"a": 1, "b": 2}'

    def test_nested_trailing_commas(self):
        raw = '{"a": [1, 2,], "b": {"c": 3,},}'
        result = extract_json(raw)
        # All trailing commas should be removed
        assert ",}" not in result
        assert ",]" not in result

    def test_no_json_returns_as_is(self):
        raw = "No JSON here, just plain text."
        result = extract_json(raw)
        assert result == raw

    def test_array_json(self):
        raw = 'Result: [1, 2, 3] end'
        result = extract_json(raw)
        assert result == "[1, 2, 3]"


# ---------------------------------------------------------------------------
# parse_ai_json
# ---------------------------------------------------------------------------

class TestParseAIJSON:
    def test_valid_json(self):
        result = parse_ai_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_wrapped_in_fences(self):
        result = parse_ai_json('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="invalid JSON"):
            parse_ai_json("not json at all", context="test")

    def test_context_in_error(self):
        with pytest.raises(ValueError, match="thesis for AAPL"):
            parse_ai_json("{broken", context="thesis for AAPL")


# ---------------------------------------------------------------------------
# validate_thesis
# ---------------------------------------------------------------------------

class TestValidateThesis:
    def test_complete_bullish_thesis(self):
        raw = {
            "ticker": "AAPL",
            "thesis": "BULLISH",
            "confidence": 0.78,
            "target_entry_price": 185.50,
            "stop_loss_price": 176.23,
            "take_profit_price": 198.00,
            "reasoning": "Strong cycle",
        }
        result = validate_thesis(raw, "AAPL")
        assert result["thesis"] == "BULLISH"
        assert result["confidence"] == 0.78
        assert result["target_entry_price"] == 185.50

    def test_missing_fields_get_defaults(self):
        raw = {"ticker": "AAPL", "thesis": "NEUTRAL"}
        result = validate_thesis(raw, "AAPL")
        assert result["confidence"] == 0.5
        assert result["reasoning"] == ""
        assert result["target_entry_price"] is None

    def test_invalid_direction_becomes_neutral(self):
        raw = {"ticker": "AAPL", "thesis": "LONG"}
        result = validate_thesis(raw, "AAPL")
        assert result["thesis"] == "NEUTRAL"

    def test_confidence_clamped_high(self):
        raw = {"ticker": "AAPL", "thesis": "NEUTRAL", "confidence": 1.5}
        result = validate_thesis(raw, "AAPL")
        assert result["confidence"] == 1.0

    def test_confidence_clamped_low(self):
        raw = {"ticker": "AAPL", "thesis": "NEUTRAL", "confidence": -0.5}
        result = validate_thesis(raw, "AAPL")
        assert result["confidence"] == 0.0

    def test_bullish_no_entry_downgrades_to_neutral(self):
        raw = {"ticker": "AAPL", "thesis": "BULLISH", "confidence": 0.8}
        result = validate_thesis(raw, "AAPL")
        assert result["thesis"] == "NEUTRAL"

    def test_bullish_no_stop_gets_default(self):
        raw = {
            "ticker": "AAPL",
            "thesis": "BULLISH",
            "confidence": 0.8,
            "target_entry_price": 100.0,
        }
        result = validate_thesis(raw, "AAPL")
        assert result["stop_loss_price"] == 95.0  # 5% below 100

    def test_ticker_forced_to_argument(self):
        raw = {"ticker": "WRONG", "thesis": "NEUTRAL"}
        result = validate_thesis(raw, "AAPL")
        assert result["ticker"] == "AAPL"

    def test_negative_price_becomes_none(self):
        raw = {
            "ticker": "AAPL",
            "thesis": "NEUTRAL",
            "target_entry_price": -10.0,
        }
        result = validate_thesis(raw, "AAPL")
        assert result["target_entry_price"] is None


class TestValidateThesisReviewMode:
    """is_review=True is used when Claude reviews a held position. In that
    mode there is no pending entry price because we already own the shares,
    so the validator must NOT downgrade BULLISH to NEUTRAL or auto-fill a
    stop-loss from an entry price we don't have.
    """

    def test_review_bullish_no_entry_stays_bullish(self):
        raw = {
            "ticker": "JPM",
            "thesis": "BULLISH",
            "confidence": 0.82,
            "review_action": "CONTINUE",
        }
        result = validate_thesis(raw, "JPM", is_review=True)
        assert result["thesis"] == "BULLISH"
        assert result["target_entry_price"] is None  # not fabricated

    def test_review_bullish_no_entry_no_stop_autofill(self):
        """Auto-fill of stop_loss depends on target_entry_price; without it
        we must leave stop_loss as None for the caller to carry forward.
        """
        raw = {
            "ticker": "JPM",
            "thesis": "BULLISH",
            "confidence": 0.8,
            "review_action": "CONTINUE",
        }
        result = validate_thesis(raw, "JPM", is_review=True)
        assert result["stop_loss_price"] is None

    def test_review_mode_still_clamps_confidence(self):
        raw = {"ticker": "JPM", "thesis": "BULLISH", "confidence": 1.5}
        result = validate_thesis(raw, "JPM", is_review=True)
        assert result["confidence"] == 1.0

    def test_review_mode_still_normalizes_direction(self):
        raw = {"ticker": "JPM", "thesis": "long"}
        result = validate_thesis(raw, "JPM", is_review=True)
        # "long" isn't a valid direction — still becomes NEUTRAL, just not for
        # the missing-entry-price reason.
        assert result["thesis"] == "NEUTRAL"

    def test_new_candidate_mode_unchanged(self):
        """Existing callers that don't pass is_review must get the old behaviour."""
        raw = {"ticker": "AAPL", "thesis": "BULLISH", "confidence": 0.8}
        result = validate_thesis(raw, "AAPL")  # default is_review=False
        assert result["thesis"] == "NEUTRAL"


# ---------------------------------------------------------------------------
# validate_sentry_signal
# ---------------------------------------------------------------------------

class TestValidateSentrySignal:
    def test_valid_continue(self):
        raw = {"signal": "CONTINUE", "reasoning": "All clear"}
        result = validate_sentry_signal(raw, "AAPL")
        assert result["signal"] == "CONTINUE"
        assert result["ticker"] == "AAPL"

    def test_valid_abort(self):
        raw = {"signal": "ABORT", "conflicting_headlines": ["Bad news"]}
        result = validate_sentry_signal(raw, "AAPL")
        assert result["signal"] == "ABORT"
        assert len(result["conflicting_headlines"]) == 1

    def test_invalid_signal_defaults_to_continue(self):
        raw = {"signal": "HOLD"}
        result = validate_sentry_signal(raw, "AAPL")
        assert result["signal"] == "CONTINUE"

    def test_missing_fields_get_defaults(self):
        result = validate_sentry_signal({}, "AAPL")
        assert result["signal"] == "CONTINUE"
        assert result["conflicting_headlines"] == []
        assert result["price_concern"] is False
        assert result["market_concern"] is False

    def test_non_list_headlines_normalized(self):
        raw = {"signal": "ABORT", "conflicting_headlines": "single string"}
        result = validate_sentry_signal(raw, "AAPL")
        assert result["conflicting_headlines"] == []


# ---------------------------------------------------------------------------
# validate_ranking
# ---------------------------------------------------------------------------

class TestValidateRanking:
    def test_valid_ranking(self):
        raw = {
            "selected_tickers": ["AAPL", "NVDA"],
            "market_regime_assessment": "Bullish",
        }
        result = validate_ranking(raw)
        assert result["selected_tickers"] == ["AAPL", "NVDA"]

    def test_empty_defaults(self):
        result = validate_ranking({})
        assert result["selected_tickers"] == []
        assert result["selections"] == []

    def test_tickers_uppercased(self):
        raw = {"selected_tickers": ["aapl", "nvda"]}
        result = validate_ranking(raw)
        assert result["selected_tickers"] == ["AAPL", "NVDA"]

    def test_non_list_tickers_normalized(self):
        raw = {"selected_tickers": "AAPL"}
        result = validate_ranking(raw)
        assert result["selected_tickers"] == []
