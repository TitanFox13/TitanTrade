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

# Approximate pricing per 1M tokens (as of 2026-03)
# Update these when model pricing changes.
_PRICING: dict[str, dict[str, float]] = {
    # Claude Sonnet 4
    "claude-sonnet-4-6-20250514": {"input": 3.00, "output": 15.00},
    # Claude Opus 4
    "claude-opus-4-6-20260301": {"input": 15.00, "output": 75.00},
    # Gemini Flash 2.0
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
