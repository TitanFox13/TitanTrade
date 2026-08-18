"""Append-only trade log + near-miss store, state loader, trade-record builders.

Extracted from executor.py (behavior-preserving).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from titantrade.config import STATE_DIR
from titantrade.logger import get_logger

log = get_logger("trade_state")


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def _load(filename: str) -> dict[str, Any]:
    path = STATE_DIR / filename
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def position_opened_after(ticker: str, generated_at: str | None) -> bool:
    """True when the ticker's current position was opened AFTER ``generated_at``
    (a thesis/review timestamp).

    Used by the ADJUST flow (ADR 056): the weekly review's stop/TP levels were
    computed for the position the analyst saw on Sunday. If the ticker exited
    and was RE-ENTERED since then, those levels belong to a position that no
    longer exists — production DVN was stopped out at the Aug 4 open,
    re-entered 42 minutes later at $43.65, and the stale ADJUST stop ($43.50,
    set for the old basis) was re-applied 0.34% below the fresh entry and
    tagged it out the next morning.

    "Opened" means the most recent entry-type BUY (weekly_thesis /
    bracket_resubmission). Pyramid ADDs enlarge an existing position — they
    must not mark it as newer than the review. Fails open (False → ADJUST
    applies as before) on missing/damaged data, since applying the analyst's
    levels is the long-standing default behavior.
    """
    if not generated_at:
        return False
    try:
        gen_ts = datetime.fromisoformat(generated_at)
    except (ValueError, TypeError):
        return False
    doc = _load("trade_log.json")
    trades = doc.get("trades", []) if isinstance(doc, dict) else (doc or [])
    for rec in reversed(trades):
        if rec.get("ticker") != ticker or rec.get("action") != "BUY":
            continue
        if rec.get("trigger") == "pyramid":
            continue
        try:
            buy_ts = datetime.fromisoformat(rec.get("timestamp", ""))
            return buy_ts > gen_ts
        except (ValueError, TypeError):
            # Malformed or naive-vs-aware mismatch — can't compare safely.
            return False
    return False


# Cap the size of append-only state files. Older records get spilled to a
# timestamped archive next to the live file. Without this the files grow
# linearly forever — production trade_log.json was approaching MBs after a
# month of churning.
MAX_LIVE_TRADES = 500


MAX_LIVE_NEAR_MISSES = 200


def _archive_overflow(filename: str, key: str, max_keep: int) -> None:
    """If the named file's list exceeds ``max_keep``, archive the oldest
    half to ``state/archive/{filename}.YYYYMMDD-HHMMSS.json`` and write back
    only the kept tail.
    """
    path = STATE_DIR / filename
    if not path.exists():
        return
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return
    items = data.get(key, [])
    if len(items) <= max_keep:
        return

    cutoff = len(items) - max_keep
    archived, kept = items[:cutoff], items[cutoff:]
    archive_dir = STATE_DIR / "archive"
    archive_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    archive_path = archive_dir / f"{path.stem}.{stamp}.json"
    with open(archive_path, "w") as f:
        json.dump({key: archived}, f, indent=2)
    data[key] = kept
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    log.info(
        f"Archived {len(archived)} old {key} from {filename} to "
        f"{archive_path.name}"
    )


def _append_trade(trade: dict[str, Any]) -> None:
    path = STATE_DIR / "trade_log.json"
    data = _load("trade_log.json")
    data.setdefault("trades", []).append(trade)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    _archive_overflow("trade_log.json", "trades", MAX_LIVE_TRADES)


def _append_near_miss(record: dict[str, Any]) -> None:
    path = STATE_DIR / "near_misses.json"
    data = _load("near_misses.json")
    data.setdefault("near_misses", []).append(record)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    _archive_overflow("near_misses.json", "near_misses", MAX_LIVE_NEAR_MISSES)


def _build_trade_context(
    ticker: str,
    data_bundle: dict[str, Any],
    sentry: dict[str, Any] | None,
) -> dict[str, Any]:
    """Extract a snapshot of market/technical context at trade time."""
    stock_data = data_bundle.get("stocks", {}).get(ticker, {})
    market = data_bundle.get("market_context", {})
    technicals = stock_data.get("technical_indicators", {})
    earnings = stock_data.get("earnings", {})
    price_vs_sma = technicals.get("price_vs_sma", {})
    macd = technicals.get("macd", {})
    spy = market.get("spy", {})

    news = stock_data.get("news", [])
    recent_headlines = [n.get("title", "") for n in news[:3]]

    return {
        "market_regime": market.get("market_regime"),
        "vix_level": market.get("vix", {}).get("level"),
        "vix_classification": market.get("vix", {}).get("classification"),
        "spy_return_1d": spy.get("return_1d"),
        "technicals": {
            "rsi_14": technicals.get("rsi_14"),
            "macd_histogram": macd.get("histogram"),
            "atr_14": stock_data.get("atr_14"),
            "price_vs_sma_50": "above" if price_vs_sma.get("above_sma_50") else "below",
            "price_vs_sma_200": "above" if price_vs_sma.get("above_sma_200") else "below",
        },
        "sentry_signal": sentry.get("signal") if sentry else None,
        "sentry_reasoning": sentry.get("reasoning") if sentry else None,
        "recent_news": recent_headlines,
        "earnings_days_away": earnings.get("days_until_earnings"),
        "sector": stock_data.get("sector") or technicals.get("sector"),
    }


def _trade_record(
    ticker: str,
    action: str,
    shares: int,
    price: float,
    trigger: str,
    reasoning: str,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "id": f"trade_{uuid.uuid4().hex[:8]}",
        "ticker": ticker,
        "action": action,
        "shares": shares,
        "price": price,
        "total_value": round(shares * price, 2) if price else 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trigger": trigger,
        "reasoning": reasoning,
        **extra,
    }


def _build_near_miss_record(
    ticker: str,
    thesis: dict[str, Any],
    entry_price: float | None,
    stop_price: float | None,
    take_profit_price: float | None,
    failed_gates: list[str],
    gate_results: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    """Build a near-miss record (a blocked/declined entry worth surfacing on the
    dashboard). Shared by the downtrend and multi-gate block paths in
    ``_handle_bullish_entry``."""
    return {
        "id": f"nm_{uuid.uuid4().hex[:8]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ticker": ticker,
        "confidence": thesis.get("confidence", 0),
        "thesis": thesis.get("thesis", ""),
        "target_entry_price": entry_price,
        "stop_loss_price": stop_price,
        "take_profit_price": take_profit_price,
        "reasoning": thesis.get("reasoning", ""),
        "failed_gates": failed_gates,
        "gate_results": gate_results,
        "total_gates_failed": len(failed_gates),
        "context": context,
    }
