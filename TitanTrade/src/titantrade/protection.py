"""Pre-flight position safety: orphan close + gap-down protection.

Extracted from executor.py (behavior-preserving).
"""

from __future__ import annotations

from typing import Any

from titantrade.logger import get_logger, log_decision
from titantrade.retry import HTTPError
from titantrade.broker import (
    get_positions, get_open_orders, cancel_order,
    cancel_all_orders_for_ticker, close_position_at_market,
    place_market_sell, _wait_for_order_canceled,
)
from titantrade.trade_state import _append_trade, _load, _trade_record
from titantrade.trailing_state import _cleanup_trailing_state
from titantrade.core_allocation import _is_core_ticker

log = get_logger("protection")


# ---------------------------------------------------------------------------
# Thesis expiry: close orphaned positions
# ---------------------------------------------------------------------------

def close_orphaned_positions(cfg: Config) -> list[dict[str, Any]]:
    """Close positions that have no active thesis. Weekly-review CLOSE actions
    on **losing** positions are downgraded to TIGHTEN_STOP — the analyst can
    only tighten the leash on a losing position, never preempt it. Stops are
    sacred; if the analyst wants out badly enough, they can tighten the stop
    so close to market that the next normal day will trigger it.

    Cases handled here:
    1. A held ticker has no entry in weekly_thesis.json (orphaned) → CLOSE
    2. review_action == "CLOSE" AND position is **in profit** → CLOSE
       (taking profit on a flipped thesis is legitimate)
    3. review_action == "CLOSE" AND position is **at a loss** → SKIP
       (would crystallize a loss the programmatic stop hasn't hit yet —
        production showed HCA closed at -1.6% via this path while its stop
        was still 4% away; let the stop do its job)

    Independently of this function, the ADJUST path (executor section 4a)
    will handle the stop-tightening when review_action=CLOSE on a loser —
    it sees the (tighter) stop_loss_price the analyst sets and replaces.
    """
    thesis_doc = _load("weekly_thesis.json")
    positions = get_positions(cfg)

    if not positions:
        return []

    # Index theses by ticker
    theses_by_ticker = {
        t["ticker"]: t for t in thesis_doc.get("theses", [])
    }

    closed: list[dict[str, Any]] = []

    for pos in positions:
        ticker = pos.get("symbol", "")
        qty = float(pos.get("qty", 0))
        if qty <= 0:
            continue

        # Core-allocation tickers (SPY, hedge ETFs) are managed by
        # manage_core_position, not by the AI thesis path. They have no
        # weekly thesis entry — but they're not "orphans" we should sell.
        if _is_core_ticker(ticker, cfg):
            continue

        thesis = theses_by_ticker.get(ticker)

        # Case 1: Position is covered by an active thesis that isn't CLOSE
        if thesis and thesis.get("review_action") != "CLOSE":
            continue

        # Case 2: Explicit CLOSE action — gate on profit/loss
        if thesis and thesis.get("review_action") == "CLOSE":
            unrealized_pl_pct = float(pos.get("unrealized_plpc", 0)) * 100
            if unrealized_pl_pct < 0:
                # CLOSE on a loser is downgraded to "let the stop work".
                # The analyst's stop_loss_price (typically tightened in the
                # CLOSE thesis) will be applied by the ADJUST path. No
                # discretionary market-sell.
                log.info(
                    f"Weekly CLOSE for {ticker} downgraded — position at "
                    f"{unrealized_pl_pct:+.1f}% (loss). Stops are sacred; "
                    f"deferring to programmatic stop. Original reasoning: "
                    f"{thesis.get('reasoning', '')[:200]}"
                )
                continue
            reason = (
                f"Weekly review: CLOSE — {thesis.get('reasoning', 'Thesis invalidated')} "
                f"(taking profit at {unrealized_pl_pct:+.1f}%)"
            )
        else:
            reason = f"No thesis entry for {ticker} in current weekly analysis"

        log.warning(f"ORPHAN CLOSE: {ticker} — {reason}")
        try:
            cancel_all_orders_for_ticker(ticker, cfg)
            close_position_at_market(ticker, cfg)
            trade = _trade_record(
                ticker=ticker,
                action="SELL",
                shares=qty,
                price=float(pos.get("current_price", 0)),
                trigger="thesis_expired",
                reasoning=reason,
            )
            _append_trade(trade)
            closed.append(trade)
            log_decision(log, "executor", ticker, "SELL (ORPHAN)", reason)
        except HTTPError as exc:
            # Surface broker diagnostics (e.g. Alpaca error code + message)
            # so the root cause is visible in logs — the next executor run
            # will retry this orphan close automatically.
            log.error(
                f"Failed to close orphaned position {ticker}: "
                f"HTTP {exc.status_code} code={exc.error_code} "
                f"msg={exc.error_message or exc.body[:200]} "
                f"— will retry on next run"
            )
        except Exception as exc:
            log.error(
                f"Failed to close orphaned position {ticker}: {exc} "
                f"— will retry on next run"
            )

    if closed:
        # Clean up trailing state for closed tickers
        _cleanup_trailing_state(
            {p["symbol"] for p in get_positions(cfg)}
        )

    return closed


# ---------------------------------------------------------------------------
# Gap-down protection: detect unfilled stop-limits after gap
# ---------------------------------------------------------------------------

def check_gap_down_protection(cfg: Config) -> list[dict[str, Any]]:
    """Detect positions where a stop-limit order failed to fill due to a gap-down.

    If the current price is below the stop-limit's limit price, the stop either:
    - Triggered but the limit didn't fill (price gapped through)
    - Hasn't triggered because price gapped below the stop itself

    In both cases the position is unprotected. Market-sell immediately.
    """
    positions = get_positions(cfg)
    if not positions:
        return []

    closed: list[dict[str, Any]] = []

    for pos in positions:
        ticker = pos.get("symbol", "")
        current_price = float(pos.get("current_price", 0))
        qty = float(pos.get("qty", 0))

        if qty <= 0 or current_price <= 0:
            continue

        open_orders = get_open_orders(ticker, cfg)
        for order in open_orders:
            if order.get("type") != "stop_limit" or order.get("side") != "sell":
                continue

            limit_price = float(order.get("limit_price", 0))
            stop_price = float(order.get("stop_price", 0))

            # Gap-down: price is below the limit price (stop-limit is stale)
            if current_price < limit_price * 0.99:
                # Cross-check the LIVE market quote before a destructive
                # market-sell. Alpaca's paper position feed can carry a
                # stale/corrupted mark — e.g. a phantom split that divides the
                # price but not the share count (observed on CRWD: position
                # marked $196 while the market traded $772) — which would trip
                # this gate and liquidate a HEALTHY position on bad data. If the
                # live quote shows price still at/above the stop, the position
                # mark is wrong: skip and leave the resting stop-limit in place.
                # A missing/failed quote falls through to the sell — never weaken
                # protection when we can't confirm (the FCX bare-position case).
                try:
                    from titantrade.daily_sentry import _fetch_current_price
                    market_price = _fetch_current_price(ticker, cfg)
                except Exception:  # noqa: BLE001
                    market_price = None
                if market_price and market_price >= stop_price:
                    log.warning(
                        f"GAP-DOWN for {ticker} NOT confirmed by live quote: "
                        f"position mark ${current_price:.2f} but market "
                        f"${market_price:.2f} >= stop ${stop_price:.2f} — "
                        f"stale/glitched position price, skipping market-sell"
                    )
                    break
                log.warning(
                    f"GAP-DOWN DETECTED: {ticker} at ${current_price:.2f} "
                    f"below stop-limit ${stop_price:.2f}/${limit_price:.2f}"
                )
                try:
                    cancel_order(order["id"], cfg)
                    # Wait for the cancel to RELEASE the held qty before the
                    # market sell. The stop-limit we just cancelled holds all
                    # the shares (held_for_orders); firing the sell immediately
                    # 403s with "insufficient qty (available: 0)". This was the
                    # production bug where gap-down protection failed to fire on
                    # FCX precisely when it was needed most. Polling the order
                    # to a terminal state guarantees the shares are free.
                    _wait_for_order_canceled(order["id"], cfg)
                    place_market_sell(ticker, qty, cfg)
                    trade = _trade_record(
                        ticker=ticker,
                        action="SELL",
                        shares=qty,
                        price=current_price,
                        trigger="gap_down_protection",
                        reasoning=(
                            f"Stop-limit at ${stop_price:.2f}/${limit_price:.2f} "
                            f"failed to fill — price gapped to ${current_price:.2f}"
                        ),
                    )
                    _append_trade(trade)
                    closed.append(trade)
                    log_decision(
                        log, "executor", ticker,
                        "SELL (GAP-DOWN)", trade["reasoning"],
                    )
                except Exception as exc:
                    log.error(f"Gap-down protection failed for {ticker}: {exc}")
                break  # Only one market sell per ticker

    return closed
