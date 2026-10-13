"""Performance tracking and feedback loop for Claude calibration.

Reads the trade log, computes win/loss stats, confidence calibration,
and generates a text summary that gets injected into the weekly analyst prompt.
This allows Claude to self-correct over time.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from titantrade.config import STATE_DIR
from titantrade.logger import get_logger

log = get_logger("performance")


def load_trade_log() -> list[dict[str, Any]]:
    """Load all trades from the trade log."""
    path = STATE_DIR / "trade_log.json"
    if not path.exists():
        return []
    with open(path) as f:
        data = json.load(f)
    return data.get("trades", [])


def load_thesis_history() -> list[dict[str, Any]]:
    """Load historical thesis records (if we've been saving them)."""
    path = STATE_DIR / "thesis_history.json"
    if not path.exists():
        return []
    with open(path) as f:
        data = json.load(f)
    return data.get("theses", [])


def save_thesis_to_history(thesis_doc: dict[str, Any]) -> None:
    """Archive a weekly thesis for future performance tracking."""
    path = STATE_DIR / "thesis_history.json"
    history = {"theses": []}
    if path.exists():
        with open(path) as f:
            history = json.load(f)

    history["theses"].append({
        "generated_at": thesis_doc.get("generated_at"),
        "theses": thesis_doc.get("theses", []),
    })

    # Keep last 52 weeks of history
    history["theses"] = history["theses"][-52:]

    with open(path, "w") as f:
        json.dump(history, f, indent=2)


def _pair_trades(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Match BUY and SELL trades into completed round-trips.

    Returns list of dicts with: ticker, entry_price, exit_price, pnl_pct,
    entry_date, exit_date, exit_trigger, confidence.
    """
    # Group trades by ticker
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in trades:
        by_ticker[t["ticker"]].append(t)

    pairs: list[dict[str, Any]] = []
    for ticker, ticker_trades in by_ticker.items():
        buys = [t for t in ticker_trades if t["action"] == "BUY"]
        sells = [t for t in ticker_trades if t["action"] == "SELL"]

        # Simple FIFO matching
        for i, buy in enumerate(buys):
            if i >= len(sells):
                break
            sell = sells[i]
            entry = buy.get("price", 0)
            exit_ = sell.get("price", 0)
            pnl_pct = ((exit_ - entry) / entry * 100) if entry > 0 else 0

            pairs.append({
                "ticker": ticker,
                "entry_price": entry,
                "exit_price": exit_,
                "pnl_pct": round(pnl_pct, 2),
                "entry_date": buy.get("timestamp", ""),
                "exit_date": sell.get("timestamp", ""),
                "exit_trigger": sell.get("trigger", ""),
                "shares": buy.get("shares", 0),
            })

    return pairs


def compute_stats(
    trades: list[dict[str, Any]], weeks: int = 4
) -> dict[str, Any]:
    """Compute performance statistics over the last N weeks.

    Returns overall stats and per-ticker breakdowns.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(weeks=weeks)
    recent = [
        t for t in trades
        if t.get("timestamp", "") >= cutoff.isoformat()
    ]

    pairs = _pair_trades(recent)

    if not pairs:
        return {
            "total_trades": 0,
            "completed_roundtrips": 0,
            "win_rate": None,
            "avg_pnl_pct": None,
            "best_trade": None,
            "worst_trade": None,
            "per_ticker": {},
            "by_exit_trigger": {},
        }

    wins = [p for p in pairs if p["pnl_pct"] > 0]

    # Per-ticker stats
    ticker_stats: dict[str, dict[str, Any]] = {}
    for p in pairs:
        t = p["ticker"]
        if t not in ticker_stats:
            ticker_stats[t] = {"trades": 0, "wins": 0, "total_pnl_pct": 0}
        ticker_stats[t]["trades"] += 1
        if p["pnl_pct"] > 0:
            ticker_stats[t]["wins"] += 1
        ticker_stats[t]["total_pnl_pct"] += p["pnl_pct"]

    for t, s in ticker_stats.items():
        s["win_rate"] = round(s["wins"] / s["trades"] * 100, 1) if s["trades"] > 0 else 0
        s["avg_pnl_pct"] = round(s["total_pnl_pct"] / s["trades"], 2) if s["trades"] > 0 else 0

    # By exit trigger
    trigger_stats: dict[str, dict[str, Any]] = {}
    for p in pairs:
        trigger = p.get("exit_trigger", "unknown")
        if trigger not in trigger_stats:
            trigger_stats[trigger] = {"count": 0, "avg_pnl": 0, "total_pnl": 0}
        trigger_stats[trigger]["count"] += 1
        trigger_stats[trigger]["total_pnl"] += p["pnl_pct"]

    for trigger, s in trigger_stats.items():
        s["avg_pnl"] = round(s["total_pnl"] / s["count"], 2) if s["count"] > 0 else 0

    all_pnl = [p["pnl_pct"] for p in pairs]

    return {
        "total_trades": len(recent),
        "completed_roundtrips": len(pairs),
        "win_rate": round(len(wins) / len(pairs) * 100, 1),
        "avg_pnl_pct": round(sum(all_pnl) / len(all_pnl), 2),
        "total_pnl_pct": round(sum(all_pnl), 2),
        "best_trade": max(pairs, key=lambda p: p["pnl_pct"]),
        "worst_trade": min(pairs, key=lambda p: p["pnl_pct"]),
        "per_ticker": ticker_stats,
        "by_exit_trigger": trigger_stats,
    }


def compute_confidence_calibration(
    trades: list[dict[str, Any]],
    thesis_history: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare AI confidence scores against actual outcomes.

    Groups theses by confidence bucket (0.5-0.6, 0.6-0.7, etc.)
    and checks actual win rate in each bucket.
    """
    # Build a map of (ticker, week) -> thesis confidence
    confidence_map: dict[str, float] = {}
    for week in thesis_history:
        week_date = week.get("generated_at", "")[:10]
        for thesis in week.get("theses", []):
            key = f"{thesis['ticker']}_{week_date}"
            confidence_map[key] = thesis.get("confidence", 0)

    # If we don't have enough data, return empty
    if not confidence_map:
        return {"buckets": {}, "note": "Insufficient thesis history for calibration"}

    pairs = _pair_trades(trades)

    buckets: dict[str, dict[str, int]] = {
        "0.50-0.60": {"total": 0, "wins": 0},
        "0.60-0.70": {"total": 0, "wins": 0},
        "0.70-0.80": {"total": 0, "wins": 0},
        "0.80-0.90": {"total": 0, "wins": 0},
        "0.90-1.00": {"total": 0, "wins": 0},
    }

    for pair in pairs:
        # Try to find matching confidence
        ticker = pair["ticker"]

        # Look for a thesis near the entry date
        matched_conf = None
        for key, conf in confidence_map.items():
            if key.startswith(f"{ticker}_"):
                matched_conf = conf
                break

        if matched_conf is None:
            continue

        # Place in bucket
        if matched_conf < 0.60:
            bucket = "0.50-0.60"
        elif matched_conf < 0.70:
            bucket = "0.60-0.70"
        elif matched_conf < 0.80:
            bucket = "0.70-0.80"
        elif matched_conf < 0.90:
            bucket = "0.80-0.90"
        else:
            bucket = "0.90-1.00"

        buckets[bucket]["total"] += 1
        if pair["pnl_pct"] > 0:
            buckets[bucket]["wins"] += 1

    # Compute actual win rates per bucket
    calibration: dict[str, dict[str, Any]] = {}
    for bucket, data in buckets.items():
        if data["total"] > 0:
            actual_rate = round(data["wins"] / data["total"] * 100, 1)
            calibration[bucket] = {
                "sample_size": data["total"],
                "actual_win_rate": actual_rate,
            }

    return {"buckets": calibration}


def generate_feedback_prompt(weeks: int = 4) -> str:
    """Generate a performance summary string to inject into Claude's prompt.

    This is the feedback loop: Claude sees how its past calls performed
    and can self-correct.
    """
    trades = load_trade_log()
    thesis_history = load_thesis_history()
    stats = compute_stats(trades, weeks=weeks)
    calibration = compute_confidence_calibration(trades, thesis_history)

    if stats["completed_roundtrips"] == 0:
        return (
            "PERFORMANCE HISTORY: No completed trades yet. "
            "This is a new trading period - no historical calibration available."
        )

    lines = [
        f"PERFORMANCE HISTORY (Last {weeks} weeks):",
        f"  Completed round-trips: {stats['completed_roundtrips']}",
        f"  Win rate: {stats['win_rate']}%",
        f"  Average P&L per trade: {stats['avg_pnl_pct']}%",
        f"  Total P&L: {stats['total_pnl_pct']}%",
    ]

    # Per-ticker breakdown
    if stats["per_ticker"]:
        lines.append("  Per-ticker performance:")
        for ticker, ts in sorted(stats["per_ticker"].items()):
            lines.append(
                f"    {ticker}: {ts['trades']} trades, "
                f"{ts['win_rate']}% win rate, "
                f"avg {ts['avg_pnl_pct']}%"
            )

    # Best and worst
    if stats["best_trade"]:
        best = stats["best_trade"]
        lines.append(f"  Best trade: {best['ticker']} +{best['pnl_pct']}%")
    if stats["worst_trade"]:
        worst = stats["worst_trade"]
        lines.append(f"  Worst trade: {worst['ticker']} {worst['pnl_pct']}%")

    # Exit trigger analysis
    if stats["by_exit_trigger"]:
        lines.append("  Exit trigger breakdown:")
        for trigger, ts in stats["by_exit_trigger"].items():
            lines.append(f"    {trigger}: {ts['count']}x, avg P&L {ts['avg_pnl']}%")

    # Confidence calibration
    if calibration.get("buckets"):
        lines.append("  Confidence calibration (your confidence vs actual win rate):")
        for bucket, data in sorted(calibration["buckets"].items()):
            lines.append(
                f"    Confidence {bucket}: "
                f"{data['actual_win_rate']}% actual win rate "
                f"(n={data['sample_size']})"
            )

    lines.append(
        "  Use this data to calibrate your confidence scores. "
        "If you have been overconfident on a ticker, lower your confidence. "
        "If you have been underconfident, consider raising it."
    )

    return "\n".join(lines)
