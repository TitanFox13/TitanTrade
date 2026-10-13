"""Append-only trade log + near-miss store, state loader, trade-record builders."""

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


def _save(filename: str, data: dict[str, Any]) -> None:
    with open(STATE_DIR / filename, "w") as f:
        json.dump(data, f, indent=2)


def _opening_buy(ticker: str) -> dict[str, Any] | None:
    """Trade-log record of the BUY that opened the ticker's current position.

    "Opened" means the most recent entry-type BUY (entry /
    bracket_resubmission); pyramid ADDs enlarge an existing position and are
    skipped. The log records submissions, so a bracket that expired and was
    resubmitted resolves to the resubmission that filled — accurate to the
    session.
    """
    doc = _load("trade_log.json")
    trades = doc.get("trades", []) if isinstance(doc, dict) else (doc or [])
    for rec in reversed(trades):
        if rec.get("ticker") != ticker or rec.get("action") != "BUY":
            continue
        if rec.get("trigger") == "pyramid":
            continue
        return rec
    return None


def position_opened_at(ticker: str) -> str | None:
    """ISO timestamp of the trade-log BUY that opened the ticker's current
    position, or None when the log has no such record (Decision 058: the
    weekly review had been telling the analyst "Days held: 0" for every
    position because broker positions carry no entry date and per-ticker
    theses no timestamp).
    """
    rec = _opening_buy(ticker)
    ts = rec.get("timestamp") if rec else None
    return ts if isinstance(ts, str) and ts else None


def position_entry_stop(ticker: str) -> float | None:
    """Stop price the opening bracket carried — the trade-log
    ``stop_loss_price`` of the BUY that opened the current position — or None
    when the log has no usable level (legacy records).

    Decision 060: this is the level to restore when a freshly filled
    bracket's DAY legs are gone, not the weekly thesis stop, which was
    computed for a position that may no longer exist.
    """
    rec = _opening_buy(ticker)
    if not rec:
        return None
    try:
        stop = float(rec.get("stop_price") or rec.get("stop_loss_price") or 0)
    except (TypeError, ValueError):
        return None
    return stop if stop > 0 else None


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


def _build_trade_context(ticker: str, data_bundle: dict[str, Any]) -> dict[str, Any]:
    """Snapshot of the inputs at trade time (for the trade log / near-misses)."""
    stock = data_bundle.get("stocks", {}).get(ticker, {}) or {}
    inputs = stock.get("signal_inputs", {}) or {}
    market = data_bundle.get("market_context", {}) or {}
    return {
        "close": inputs.get("close"),
        "high_lookback": inputs.get("high_lookback"),
        "sma_trend": inputs.get("sma_trend"),
        "atr_14": stock.get("atr_14"),
        "earnings_days_away": (stock.get("earnings") or {}).get("days_until_earnings"),
        "sector": stock.get("sector"),
        "spy_return_5d": (market.get("spy") or {}).get("return_5d"),
        "sector_breadth": (market.get("breadth") or {}).get("pct"),
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
    item: dict[str, Any],
    failed_gates: list[str],
    gate_results: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    """A blocked entry worth surfacing (≤ 2 failing gates)."""
    return {
        "id": f"nm_{uuid.uuid4().hex[:8]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ticker": item.get("ticker"),
        "dip_pct": item.get("dip_pct"),
        "entry_price": item.get("entry_price"),
        "stop_price": item.get("stop_price"),
        "target_price": item.get("target_price"),
        "reason": item.get("reason", ""),
        "failed_gates": failed_gates,
        "gate_results": gate_results,
        "total_gates_failed": len(failed_gates),
        "context": context,
    }
