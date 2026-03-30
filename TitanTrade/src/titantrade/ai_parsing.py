"""Robust AI response parsing with schema validation.

AI models sometimes return:
  - Valid JSON wrapped in markdown code fences
  - JSON with extra text before/after
  - JSON with trailing commas (invalid but common)
  - Completely malformed text
  - JSON with wrong field names

This module handles all of these gracefully.
"""

from __future__ import annotations

import json
import re
from typing import Any

from titantrade.logger import get_logger

log = get_logger("ai_parsing")


def extract_json(text: str) -> str:
    """Extract JSON from AI response text, handling common formatting issues.

    Tries in order:
      1. Strip markdown code fences
      2. Find first { ... } or [ ... ] block
      3. Remove trailing commas before } or ]
    """
    text = text.strip()

    # Strip markdown code fences: ```json ... ``` or ``` ... ```
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end]).strip()

    # If there's text before the JSON, find the first { or [
    first_brace = text.find("{")
    first_bracket = text.find("[")

    if first_brace == -1 and first_bracket == -1:
        return text  # No JSON found, return as-is for error handling

    # Pick whichever comes first
    if first_brace == -1:
        start = first_bracket
    elif first_bracket == -1:
        start = first_brace
    else:
        start = min(first_brace, first_bracket)

    # Find the matching closing brace/bracket from the end
    if text[start] == "{":
        end = text.rfind("}") + 1
    else:
        end = text.rfind("]") + 1

    if end <= start:
        return text  # Can't find matching close

    text = text[start:end]

    # Remove trailing commas before } or ] (common AI mistake)
    text = re.sub(r",\s*([}\]])", r"\1", text)

    return text


def parse_ai_json(
    text: str,
    context: str = "AI response",
) -> dict[str, Any] | list[Any]:
    """Parse JSON from AI response with robust error handling.

    Returns parsed JSON or raises ValueError with helpful context.
    """
    cleaned = extract_json(text)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        # Log the raw response for debugging
        log.error(
            f"Failed to parse JSON from {context}. "
            f"Error: {exc}. "
            f"Raw text (first 500 chars): {text[:500]}"
        )
        raise ValueError(
            f"AI returned invalid JSON ({context}): {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Schema validators for specific AI outputs
# ---------------------------------------------------------------------------

THESIS_REQUIRED_FIELDS = {"ticker", "thesis"}
THESIS_DEFAULTS = {
    "thesis": "NEUTRAL",
    "confidence": 0.5,
    "target_entry_price": None,
    "stop_loss_price": None,
    "take_profit_price": None,
    "thesis_breach_condition": "",
    "key_technical_levels": {},
    "reasoning": "",
    "sector": "Unknown",
    "hold_horizon": "short_term",
    "review_action": "NEW",
}

VALID_THESIS_VALUES = {"BULLISH", "BEARISH", "NEUTRAL"}
VALID_HOLD_HORIZONS = {"short_term", "medium_term", "long_term"}
VALID_REVIEW_ACTIONS = {"NEW", "CONTINUE", "ADJUST", "CLOSE"}

SENTRY_DEFAULTS = {
    "signal": "CONTINUE",
    "conflicting_headlines": [],
    "price_concern": False,
    "market_concern": False,
    "reasoning": "",
}

VALID_SIGNAL_VALUES = {"CONTINUE", "ABORT"}

RANKING_DEFAULTS = {
    "selected_tickers": [],
    "market_regime_assessment": "",
    "selections": [],
    "rejections": [],
    "portfolio_risk_notes": "",
}


def validate_thesis(raw: dict[str, Any], ticker: str) -> dict[str, Any]:
    """Validate and normalize a thesis response from Claude.

    Fills missing fields with defaults, corrects invalid values.
    """
    result = {**THESIS_DEFAULTS, **raw}

    # Ensure ticker is correct (AI might echo wrong ticker)
    result["ticker"] = ticker

    # Validate thesis direction
    thesis_val = str(result["thesis"]).upper().strip()
    if thesis_val not in VALID_THESIS_VALUES:
        log.warning(
            f"Invalid thesis value '{result['thesis']}' for {ticker}, "
            f"defaulting to NEUTRAL"
        )
        thesis_val = "NEUTRAL"
    result["thesis"] = thesis_val

    # Validate confidence range
    try:
        conf = float(result["confidence"])
        result["confidence"] = max(0.0, min(1.0, conf))
    except (ValueError, TypeError):
        result["confidence"] = 0.5

    # Validate prices are positive numbers or None
    for field in ("target_entry_price", "stop_loss_price", "take_profit_price"):
        val = result.get(field)
        if val is not None:
            try:
                val = float(val)
                result[field] = val if val > 0 else None
            except (ValueError, TypeError):
                result[field] = None

    # If BULLISH but missing entry price, downgrade to NEUTRAL
    if result["thesis"] == "BULLISH" and result["target_entry_price"] is None:
        log.warning(f"BULLISH thesis for {ticker} has no entry price - downgrading to NEUTRAL")
        result["thesis"] = "NEUTRAL"

    # If BULLISH but missing stop-loss, calculate from entry
    if (
        result["thesis"] == "BULLISH"
        and result["target_entry_price"] is not None
        and result["stop_loss_price"] is None
    ):
        result["stop_loss_price"] = round(result["target_entry_price"] * 0.95, 2)
        log.warning(f"Missing stop-loss for {ticker} - defaulting to 5% below entry")

    # Validate hold_horizon
    horizon = str(result.get("hold_horizon", "short_term")).lower().strip()
    if horizon not in VALID_HOLD_HORIZONS:
        horizon = "short_term"
    result["hold_horizon"] = horizon

    # Validate review_action
    action = str(result.get("review_action", "NEW")).upper().strip()
    if action not in VALID_REVIEW_ACTIONS:
        action = "NEW"
    result["review_action"] = action

    return result


def validate_sentry_signal(raw: dict[str, Any], ticker: str) -> dict[str, Any]:
    """Validate and normalize a sentry signal from Gemini."""
    result = {**SENTRY_DEFAULTS, **raw}
    result["ticker"] = ticker

    signal_val = str(result["signal"]).upper().strip()
    if signal_val not in VALID_SIGNAL_VALUES:
        log.warning(
            f"Invalid sentry signal '{result['signal']}' for {ticker}, "
            f"defaulting to CONTINUE"
        )
        signal_val = "CONTINUE"
    result["signal"] = signal_val

    # Ensure conflicting_headlines is a list
    if not isinstance(result["conflicting_headlines"], list):
        result["conflicting_headlines"] = []

    return result


def validate_ranking(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize the Pass 2 ranking response."""
    result = {**RANKING_DEFAULTS, **raw}

    # Ensure selected_tickers is a list of strings
    if not isinstance(result["selected_tickers"], list):
        result["selected_tickers"] = []
    result["selected_tickers"] = [
        str(t).upper() for t in result["selected_tickers"]
    ]

    return result
