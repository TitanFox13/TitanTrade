"""Operational cost tracker - logs AI API usage and estimated costs.

Writes to state/costs.json. Each API call (Claude, Gemini) is recorded
with token counts and estimated USD cost based on published pricing.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from titantrade.config import STATE_DIR

# Approximate pricing per 1M tokens (as of 2026-06). Keys are matched EXACTLY
# against the model string passed to log_cost — keep them in sync with the
# model IDs in config.py. Update when model pricing changes.
_PRICING: dict[str, dict[str, float]] = {
    # Claude (current)
    "claude-opus-4-8": {"input": 5.00, "output": 25.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    # Claude (retired — kept so historical cost records price correctly)
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    # Gemini
    "gemini-3.1-flash-lite": {"input": 0.25, "output": 1.50},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
}

# Fallback pricing if model not in table
_DEFAULT_PRICING = {"input": 5.00, "output": 15.00}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost from token counts and model pricing."""
    rates = _PRICING.get(model, _DEFAULT_PRICING)
    cost = (input_tokens / 1_000_000) * rates["input"] + \
           (output_tokens / 1_000_000) * rates["output"]
    return round(cost, 6)


def log_cost(
    service: str,
    model: str,
    description: str,
    input_tokens: int,
    output_tokens: int,
    run_type: str = "",
) -> None:
    """Append a cost record to state/costs.json.

    Args:
        service: "claude" or "gemini"
        model: Model identifier (e.g., "claude-sonnet-4-6-20250514")
        description: Human-readable label (e.g., "Weekly Pass 1: AAPL")
        input_tokens: Prompt/input token count
        output_tokens: Completion/output token count
        run_type: "weekly_analyst" or "daily_sentry"
    """
    path = STATE_DIR / "costs.json"

    if path.exists():
        with open(path) as f:
            data = json.load(f)
    else:
        data = {}

    record: dict[str, Any] = {
        "id": f"cost_{uuid.uuid4().hex[:8]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": service,
        "model": model,
        "description": description,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": _estimate_cost(model, input_tokens, output_tokens),
    }
    if run_type:
        record["run_type"] = run_type

    data.setdefault("costs", []).append(record)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
