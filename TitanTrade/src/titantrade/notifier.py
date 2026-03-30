"""Discord webhook notifications for job alerts and daily summaries."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from .config import STATE_DIR

log = logging.getLogger("titantrade.notifier")

# Discord embed color codes
COLOR_SUCCESS = 0x2ECC71  # green
COLOR_FAILURE = 0xE74C3C  # red
COLOR_SUMMARY = 0x3498DB  # blue


def _get_webhook_url() -> str | None:
    url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    return url if url else None


def send_discord(
    title: str,
    description: str = "",
    color: int = COLOR_SUMMARY,
    fields: list[dict[str, str]] | None = None,
) -> None:
    """Send a Discord embed via webhook. No-op if webhook URL is not configured."""
    url = _get_webhook_url()
    if not url:
        return

    embed: dict[str, Any] = {
        "title": title,
        "color": color,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if description:
        embed["description"] = description
    if fields:
        embed["fields"] = fields

    payload = {"embeds": [embed]}

    try:
        resp = httpx.post(url, json=payload, timeout=5.0)
        if resp.status_code >= 400:
            log.warning(f"Discord webhook returned {resp.status_code}: {resp.text[:200]}")
    except Exception:
        log.exception("Failed to send Discord notification")


def notify_job_completed(job_name: str, result: str | None, duration_seconds: float) -> None:
    """Send a green success notification for a completed job."""
    fields = []
    if result:
        fields.append({"name": "Result", "value": result, "inline": True})
    fields.append({"name": "Duration", "value": f"{duration_seconds:.0f}s", "inline": True})

    send_discord(
        title=f"Job completed: {job_name}",
        color=COLOR_SUCCESS,
        fields=fields,
    )


def notify_job_failed(job_name: str, error: str, duration_seconds: float) -> None:
    """Send a red failure notification for a failed job."""
    # Truncate long error messages for Discord's field limit
    error_text = error[:1000] if len(error) > 1000 else error

    send_discord(
        title=f"Job failed: {job_name}",
        color=COLOR_FAILURE,
        fields=[
            {"name": "Error", "value": f"```{error_text}```", "inline": False},
            {"name": "Duration", "value": f"{duration_seconds:.0f}s", "inline": True},
        ],
    )


def _load_state(filename: str) -> Any:
    """Load a state JSON file, returning None if missing."""
    path = STATE_DIR / filename
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def send_daily_summary() -> str:
    """Build and send a daily portfolio summary to Discord.

    Returns a status string for the scheduler job history.
    """
    fields: list[dict[str, str]] = []

    # --- Portfolio ---
    portfolio = _load_state("portfolio.json")
    if portfolio:
        total = portfolio.get("portfolio_value") or portfolio.get("equity")
        cash = portfolio.get("cash")
        if total is not None:
            fields.append({
                "name": "Portfolio Value",
                "value": f"${total:,.2f}" if isinstance(total, (int, float)) else str(total),
                "inline": True,
            })
        if cash is not None:
            fields.append({
                "name": "Cash",
                "value": f"${cash:,.2f}" if isinstance(cash, (int, float)) else str(cash),
                "inline": True,
            })

    # --- Open positions ---
    positions = portfolio.get("positions", []) if portfolio else []
    if positions:
        lines = []
        for p in positions[:10]:  # cap at 10 to avoid embed overflow
            ticker = p.get("symbol", p.get("ticker", "?"))
            pnl = p.get("unrealized_plpc") or p.get("change_pct")
            if pnl is not None:
                try:
                    pnl_val = float(pnl) * 100
                    sign = "+" if pnl_val >= 0 else ""
                    lines.append(f"{ticker} {sign}{pnl_val:.1f}%")
                except (ValueError, TypeError):
                    lines.append(ticker)
            else:
                lines.append(ticker)
        fields.append({
            "name": f"Positions ({len(positions)})",
            "value": ", ".join(lines) if lines else "none",
            "inline": False,
        })

    # --- Trailing stops ---
    trailing = _load_state("trailing_stops.json")
    if trailing:
        active = [t for t in trailing.values() if isinstance(t, dict) and t.get("active")]
        if active:
            ts_lines = []
            for t in active[:5]:
                ticker = t.get("ticker", "?")
                trail = t.get("trail_price")
                ts_lines.append(f"{ticker} (trail ${trail:,.2f})" if trail else ticker)
            fields.append({
                "name": f"Trailing Stops ({len(active)})",
                "value": ", ".join(ts_lines),
                "inline": False,
            })

    # --- Today's sentry signals ---
    sentry = _load_state("sentry_signals.json")
    if sentry:
        signals = sentry.get("signals", [])
        if signals:
            continue_count = sum(1 for s in signals if s.get("signal") == "CONTINUE")
            abort_count = sum(1 for s in signals if s.get("signal") == "ABORT")
            abort_tickers = [s.get("ticker", "?") for s in signals if s.get("signal") == "ABORT"]
            sig_text = f"CONTINUE x{continue_count}"
            if abort_count:
                sig_text += f", ABORT x{abort_count} ({', '.join(abort_tickers)})"
            fields.append({
                "name": "Sentry Signals",
                "value": sig_text,
                "inline": False,
            })

    # --- Today's trades ---
    trade_log = _load_state("trade_log.json")
    if trade_log:
        trades = trade_log if isinstance(trade_log, list) else trade_log.get("trades", [])
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        todays_trades = [
            t for t in trades
            if t.get("timestamp", "").startswith(today) or t.get("date", "").startswith(today)
        ]
        if todays_trades:
            trade_lines = []
            for t in todays_trades[:5]:
                action = t.get("action", "?")
                ticker = t.get("ticker", "?")
                qty = t.get("shares") or t.get("qty", "")
                price = t.get("price", "")
                line = f"{action} {ticker}"
                if qty:
                    line += f" x{qty}"
                if price:
                    line += f" @ ${price}"
                trade_lines.append(line)
            fields.append({
                "name": f"Trades Today ({len(todays_trades)})",
                "value": "\n".join(trade_lines),
                "inline": False,
            })

    # --- Trading mode ---
    from .config import load_watchlist
    settings = load_watchlist()
    fields.append({
        "name": "Mode",
        "value": settings.trading_mode.upper(),
        "inline": True,
    })

    if not fields:
        return "no state data available"

    send_discord(
        title="TitanTrade Daily Summary",
        color=COLOR_SUMMARY,
        fields=fields,
    )
    return "daily summary sent"
