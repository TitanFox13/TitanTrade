"""Lightweight intraday price checks — zero LLM cost.

Runs between the 09:00 and 15:30 sentry runs to close the time gap.
Pure price-based: checks adverse stock moves and SPY drops.
No Gemini calls, no token spend.

Usage:
    python -m titantrade pricecheck

Suggested cron (every 2 hours during market hours):
    0 11,13,15 * * 1-5  docker compose run --rm titantrade pricecheck
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from titantrade.config import Config, STATE_DIR, load_config
from titantrade.daily_sentry import (
    MARKET_DROP_ALERT_PCT,
    PRICE_MOVE_ABORT_PCT,
    _fetch_current_price,
    _fetch_spy_quote,
)
from titantrade.executor import (
    _append_trade,
    _trade_record,
    cancel_all_orders_for_ticker,
    close_position_at_market,
    get_position,
    get_positions,
)
from titantrade.logger import get_logger, log_decision

log = get_logger("price_check")


def run_price_check(cfg: Config) -> dict[str, Any]:
    """Check prices for held positions and SPY. Abort on adverse moves.

    Layers (no LLM):
      1. SPY drop >2% → abort ALL positions
      2. Per-stock: 3%+ adverse move from entry → abort that position
    """
    log.info("Starting intraday price check")

    thesis_doc: dict[str, Any] = {}
    thesis_path = STATE_DIR / "weekly_thesis.json"
    if thesis_path.exists():
        with open(thesis_path) as f:
            thesis_doc = json.load(f)

    theses_by_ticker = {
        t["ticker"]: t for t in thesis_doc.get("theses", [])
    }

    positions = get_positions(cfg)
    if not positions:
        log.info("No open positions — nothing to check")
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "spy_change_pct": None,
            "market_stress": False,
            "positions_checked": 0,
            "aborts": 0,
            "actions": [],
        }

    # Layer 1: SPY check
    spy_change = _fetch_spy_quote(cfg)
    market_stress = spy_change is not None and spy_change <= -MARKET_DROP_ALERT_PCT

    if market_stress:
        log.warning(f"MARKET STRESS: SPY {spy_change:+.1f}% — aborting all positions")

    actions: list[dict[str, Any]] = []

    for pos in positions:
        ticker = pos.get("symbol", "")
        qty = float(pos.get("qty", 0))
        current_price = float(pos.get("current_price", 0))

        if qty <= 0 or current_price <= 0:
            continue

        # Use actual avg entry price from broker (more accurate than thesis)
        entry_price = float(pos.get("avg_entry_price", 0))
        thesis = theses_by_ticker.get(ticker, {})
        direction = thesis.get("thesis", "BULLISH")  # Default to bullish for held positions

        should_abort = False
        reason = ""

        # SPY-triggered abort
        if market_stress:
            should_abort = True
            reason = f"Market stress: SPY {spy_change:+.1f}%"

        # Per-stock adverse move check
        if entry_price > 0 and not should_abort:
            move_pct = (current_price - entry_price) / entry_price * 100
            if direction == "BULLISH" and move_pct <= -PRICE_MOVE_ABORT_PCT:
                should_abort = True
                reason = (
                    f"Adverse move: ${entry_price:.2f} -> ${current_price:.2f} "
                    f"({move_pct:+.1f}%)"
                )

        if not should_abort:
            continue

        # Execute abort
        log.warning(f"PRICE CHECK ABORT: {ticker} — {reason}")
        try:
            cancel_all_orders_for_ticker(ticker, cfg)
            close_position_at_market(ticker, cfg)
            trade = _trade_record(
                ticker=ticker,
                action="SELL",
                shares=qty,
                price=current_price,
                trigger="price_check_abort",
                reasoning=reason,
            )
            _append_trade(trade)
            actions.append(trade)
            log_decision(log, "price_check", ticker, "SELL (PRICE CHECK)", reason)
        except Exception as exc:
            log.error(f"Price check abort failed for {ticker}: {exc}")

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "spy_change_pct": spy_change,
        "market_stress": market_stress,
        "positions_checked": len(positions),
        "aborts": len(actions),
        "actions": actions,
    }

    # Save for audit trail
    path = STATE_DIR / "pricecheck_signals.json"
    with open(path, "w") as f:
        json.dump(result, f, indent=2)

    log.info(
        f"Price check complete: {len(positions)} checked, "
        f"{len(actions)} aborts | SPY {spy_change or 0:+.1f}%"
    )

    return result


def main() -> None:
    cfg = load_config()
    result = run_price_check(cfg)

    spy = result.get("spy_change_pct")
    print(f"SPY: {spy or 0:+.1f}%  {'STRESS' if result.get('market_stress') else 'OK'}")
    print(f"Checked: {result.get('positions_checked', 0)} | Aborts: {result.get('aborts', 0)}")

    for a in result.get("actions", []):
        print(f"  ABORT {a['ticker']}: {a.get('reasoning', '')[:80]}")


if __name__ == "__main__":
    main()
