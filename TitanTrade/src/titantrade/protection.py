"""Pre-flight position safety: orphan close + gap-down protection (Decisions 037/054/063)."""

from __future__ import annotations

from typing import Any

from titantrade.config import Config
from titantrade.logger import get_logger, log_decision
from titantrade.retry import HTTPError
from titantrade.broker import (
    get_positions, get_position, get_open_orders, cancel_order,
    close_position_at_market, place_market_sell, place_native_stop_loss,
    _wait_for_order_canceled, get_recent_split_announcements,
)
from titantrade.market_data import get_latest_price
from titantrade.trade_state import _append_trade, _load, _trade_record
from titantrade.core_allocation import _is_core_ticker

log = get_logger("protection")

# Gap size (fraction below the stop price) beyond which a "gap-down" is more
# plausibly a stock split the broker hasn't applied to the position yet than
# a real overnight crash. The CRWD 4:1 split traded at $192.67 against a $661
# stop (71% below); organic overnight gaps on large-cap equities don't come
# close. Above this threshold we consult the corporate-actions feed before
# liquidating.
SPLIT_SUSPECT_GAP_PCT = 0.30


# ---------------------------------------------------------------------------
# Settled close — the one way a position is sold at market
# ---------------------------------------------------------------------------

def close_position_settled(ticker: str, cfg: Config, *, trigger: str, reason: str) -> dict[str, Any] | None:
    """Cancel resting orders, wait for each to settle, market-sell, record.

    The protective stop holds the shares, so a close fired right after the
    cancel 403s with "insufficient qty available" (ADR 037/042; production
    2026-10-13: three orphan closes failed exactly this way and left the
    positions without stops). On a failed close the stop is restored so the
    position is never left naked. Returns the trade record, or None.
    """
    open_orders = get_open_orders(ticker, cfg)
    for order in open_orders:
        try:
            cancel_order(order["id"], cfg)
        except Exception as exc:  # noqa: BLE001
            log.warning(f"{trigger} {ticker}: cancel {order.get('id')} failed: {exc}")
    for order in open_orders:
        _wait_for_order_canceled(order["id"], cfg)
    position = get_position(ticker, cfg)
    if not position:
        return None
    qty = float(position.get("qty") or 0)
    if qty <= 0:
        return None
    try:
        close_position_at_market(ticker, cfg)
    except Exception as exc:  # noqa: BLE001
        log.error(f"{trigger} close failed for {ticker}: {exc} — restoring stop")
        stop = next(
            (float(o.get("stop_price") or 0) for o in open_orders
             if o.get("type") in ("stop", "stop_limit") and o.get("side") == "sell"),
            0.0,
        )
        if stop > 0:
            try:
                place_native_stop_loss(ticker, qty, stop, cfg)
            except Exception as rexc:  # noqa: BLE001
                log.error(f"CRITICAL: {ticker} is naked — stop restore failed: {rexc}")
        return None
    trade = _trade_record(
        ticker=ticker, action="SELL", shares=qty,
        price=float(position.get("current_price") or 0),
        trigger=trigger, reasoning=reason,
    )
    _append_trade(trade)
    log_decision(log, "executor", ticker, f"SELL ({trigger})", reason)
    return trade


# ---------------------------------------------------------------------------
# Orphan close: a held overlay name without a plan item
# ---------------------------------------------------------------------------

def close_orphaned_positions(cfg: Config) -> list[dict[str, Any]]:
    """Market-sell every held overlay position that has no item in the plan:
    positions opened before the mechanical strategy started, names removed
    from the watchlist, or anything else the plan does not own. The core ETF
    is never an orphan. Returns the trade records."""
    plan = _load("plan.json")
    positions = get_positions(cfg)
    if not positions:
        return []
    planned = {i.get("ticker") for i in plan.get("items", []) if i.get("ticker")}
    closed: list[dict[str, Any]] = []
    for pos in positions:
        ticker = pos.get("symbol", "")
        if float(pos.get("qty", 0)) <= 0 or _is_core_ticker(ticker, cfg) or ticker in planned:
            continue
        reason = f"No plan item for {ticker} — not a position of the mechanical strategy"
        log.warning(f"ORPHAN CLOSE: {ticker} — {reason}")
        try:
            trade = close_position_settled(ticker, cfg, trigger="orphan_close", reason=reason)
        except HTTPError as exc:
            log.error(f"Failed to close orphaned position {ticker}: HTTP {exc.status_code} code={exc.error_code} msg={exc.error_message or exc.body[:200]} — will retry on next run")
            continue
        except Exception as exc:  # noqa: BLE001
            log.error(f"Failed to close orphaned position {ticker}: {exc} — will retry on next run")
            continue
        if trade:
            closed.append(trade)
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
                    market_price = get_latest_price(ticker, cfg)
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
                # A live quote below the stop confirms the *price* is real —
                # but it can still be a split artifact: on CRWD's 4:1 split
                # the market genuinely traded at $192.67 while the pre-split
                # stop sat at $661, and Alpaca paper applied the position
                # adjustment three trading days late. This gate sold the
                # (healthy) position at that artificial bottom (2026-07-02).
                # For a gap this deep, check the corporate-actions feed: a
                # recent split announcement means the position basis/stop are
                # stale, not the market — skip and alert; the broker's split
                # processing will reconcile the position. A feed error falls
                # through to the sell — never weaken protection on missing
                # data (same posture as the live-quote check above).
                effective_price = market_price or current_price
                if effective_price < stop_price * (1 - SPLIT_SUSPECT_GAP_PCT):
                    try:
                        splits = get_recent_split_announcements(ticker, cfg)
                    except Exception:  # noqa: BLE001
                        splits = []
                    if splits:
                        ann = splits[0]
                        # Alpaca announces a 4-for-1 split as new_rate=4,
                        # old_rate=1 — display in the conventional "4:1" order.
                        rate_info = (
                            f"{ann.get('new_rate', '?')}:{ann.get('old_rate', '?')}"
                        )
                        log.warning(
                            f"GAP-DOWN for {ticker} looks like a STOCK SPLIT "
                            f"(${effective_price:.2f} vs stop ${stop_price:.2f}, "
                            f"announcement rate {rate_info}) — skipping "
                            f"market-sell, awaiting broker split processing"
                        )
                        try:
                            from titantrade.notifier import notify_split_suspected
                            notify_split_suspected(
                                ticker, effective_price, stop_price, rate_info,
                            )
                        except Exception:  # noqa: BLE001
                            log.exception("Failed to send split-guard alert")
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
