"""Discord webhook notifications for job alerts and daily summaries."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from .config import STATE_DIR

log = logging.getLogger("titantrade.notifier")

# Discord embed color codes
COLOR_SUCCESS = 0x2ECC71  # green
COLOR_FAILURE = 0xE74C3C  # red
COLOR_SUMMARY = 0x3498DB  # blue
COLOR_STRATEGY = 0xF39C12  # orange — v2-strategy events (pyramid, tp1, core, override)


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


def notify_stuck_in_cash(cash_pct: float, days: int, equity: float) -> None:
    """Alert when the bot has been mostly in cash for an extended period.

    A bot that's >70% cash for >3 days is either correct (genuine bear
    market) or broken (entries failing, theses missing, macro blackouts).
    Either way, the operator should know.
    """
    send_discord(
        title=f"Stuck in cash — {cash_pct:.0f}% for {days}+ days",
        description=(
            "The bot has been heavily in cash without redeploying. Either the "
            "market regime is genuinely defensive, or new entries are being "
            "blocked (macro blackout, low confidence, qty races, etc.). "
            "Check the latest executor logs."
        ),
        color=COLOR_FAILURE,
        fields=[
            {"name": "Cash %", "value": f"{cash_pct:.1f}%", "inline": True},
            {"name": "Days stuck", "value": str(days), "inline": True},
            {"name": "Equity", "value": f"${equity:,.0f}", "inline": True},
        ],
    )


def notify_ticker_churn(ticker: str, round_trips: int, window_days: int) -> None:
    """Alert when a ticker has round-tripped (buy→sell) more than expected
    within a short window. Indicates whipsaw — either the sentry is too
    sensitive or the thesis is wrong.
    """
    send_discord(
        title=f"Ticker churn — {ticker} round-tripped {round_trips}x",
        description=(
            f"In the last {window_days} days we have bought and exited "
            f"{ticker} {round_trips} times. This is the 'sell low, buy higher' "
            f"pattern. The cooldown should suppress this — investigate."
        ),
        color=COLOR_FAILURE,
        fields=[
            {"name": "Ticker", "value": ticker, "inline": True},
            {"name": "Round trips", "value": str(round_trips), "inline": True},
            {"name": "Window", "value": f"{window_days} days", "inline": True},
        ],
    )


def notify_sentry_degraded(fallback_count: int, total: int, run_type: str) -> None:
    """Alert when Gemini is down and the sentry's news-based layer is offline.

    ``fallback_count`` is the number of tickers whose sentry check threw an
    exception and defaulted to a heuristic CONTINUE/ABORT. When this ratio is
    high the operator should know — otherwise a bad-news event could slip past
    the sentry unnoticed.
    """
    ratio = (fallback_count / total) if total else 0.0
    send_discord(
        title="Sentry degraded — news-based layer offline",
        description=(
            f"{fallback_count}/{total} sentry checks fell back to heuristic "
            f"defaults ({ratio:.0%}). Gemini may be rate-limited or down. "
            f"Price-based ABORT protection still active."
        ),
        color=COLOR_FAILURE,
        fields=[
            {"name": "Run", "value": run_type, "inline": True},
            {"name": "Failed / Total", "value": f"{fallback_count} / {total}", "inline": True},
            {"name": "Fallback rate", "value": f"{ratio:.0%}", "inline": True},
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


# ---------------------------------------------------------------------------
# Strategy v2 events — pyramid, TP1, core rebalance, cooldown override
# ---------------------------------------------------------------------------

def notify_pyramid_added(
    ticker: str, add_shares: int, add_price: float,
    existing_shares: int, gain_pct: float,
) -> None:
    """Pyramid fired: added to a winning position.

    Important enough to see in real time — pyramids concentrate capital
    in a working trade and are by design more aggressive than the initial
    bracket. Operator should know each time.
    """
    send_discord(
        title=f"Pyramid ▲ {ticker} — adding to winner",
        description=(
            f"Position is +{gain_pct:.1%} and the trailing stop is active. "
            f"Adding {add_shares} shares (~50% of original notional) on top of "
            f"the existing {existing_shares}. Stop remains the safety net; "
            f"downside is bounded at breakeven or better."
        ),
        color=COLOR_STRATEGY,
        fields=[
            {"name": "Ticker", "value": ticker, "inline": True},
            {"name": "Added", "value": f"{add_shares} @ ${add_price:.2f}", "inline": True},
            {"name": "Gain", "value": f"+{gain_pct:.1%}", "inline": True},
        ],
    )


def notify_tp1_partial(
    ticker: str, sold_shares: int, sold_price: float,
    remaining_shares: int, gain_pct: float,
) -> None:
    """TP1 partial sell fired: 1/3 of position taken at 50% of upside-to-TP,
    stop raised to breakeven on the rest.
    """
    send_discord(
        title=f"TP1 partial — {ticker} de-risked",
        description=(
            f"Sold {sold_shares} shares of {ticker} at ${sold_price:.2f} "
            f"(+{gain_pct:.1%} on those shares). Remaining {remaining_shares} "
            f"shares are now protected by a breakeven stop — runs free toward "
            f"the full take-profit target."
        ),
        color=COLOR_STRATEGY,
        fields=[
            {"name": "Ticker", "value": ticker, "inline": True},
            {"name": "Sold", "value": f"{sold_shares} @ ${sold_price:.2f}", "inline": True},
            {"name": "Remaining", "value": str(remaining_shares), "inline": True},
        ],
    )


def notify_core_rebalance(
    action: str, ticker: str, shares: int, price: float,
    target_value: float, current_value: float, stress: bool,
) -> None:
    """Core SPY/SH allocation was rebalanced. Includes the stress-swap case
    when we flip between SPY and SH (inverse).
    """
    direction = "▲ BUY" if action == "BUY" else "▼ SELL"
    send_discord(
        title=f"Core rebalance — {direction} {ticker}",
        description=(
            f"Maintaining always-on baseline allocation. "
            f"{'Market stress detected — holding hedge ETF.' if stress else 'Normal regime — holding index ETF.'}"
        ),
        color=COLOR_STRATEGY,
        fields=[
            {"name": "Action", "value": f"{direction} {shares} {ticker}", "inline": True},
            {"name": "Price", "value": f"${price:.2f}", "inline": True},
            {"name": "Target / current", "value": f"${target_value:,.0f} / ${current_value:,.0f}", "inline": False},
        ],
    )


def notify_cooldown_override(
    ticker: str, hours_since_abort: float, current_price: float, stop_price: float,
) -> None:
    """The 72h ABORT cooldown was overridden because sentry CONTINUE + price
    recovered above stop. Rare event, important to log on Discord so the
    operator knows we're re-entering a recently-stopped ticker.
    """
    send_discord(
        title=f"Cooldown override — re-entering {ticker}",
        description=(
            f"This ticker ABORTed {hours_since_abort:.0f}h ago, but: sentry "
            f"says CONTINUE, thesis still BULLISH, and price has recovered "
            f"to ${current_price:.2f} (>1% above stop ${stop_price:.2f}). "
            f"Re-entering — the original whipsaw lockout has been bypassed."
        ),
        color=COLOR_STRATEGY,
        fields=[
            {"name": "Ticker", "value": ticker, "inline": True},
            {"name": "Hours since ABORT", "value": f"{hours_since_abort:.0f}h", "inline": True},
            {"name": "Recovery", "value": f"${current_price:.2f} vs stop ${stop_price:.2f}", "inline": True},
        ],
    )
