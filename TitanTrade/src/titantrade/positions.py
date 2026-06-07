"""Open-position management: ATR trailing stop, tranched take-profit (TP1),
and pyramiding into winners. Extracted from executor.py (behavior-preserving).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from titantrade.config import Config
from titantrade.logger import get_logger
from titantrade.broker import (
    place_native_stop_loss, place_market_sell, place_limit_buy, cancel_order,
    cancel_all_orders_for_ticker, get_position, get_open_orders,
    _wait_for_order_canceled, _is_fractional,
)
from titantrade.trade_state import _append_trade, _trade_record
from titantrade.trailing_state import _load_trailing_state, _save_trailing_state

log = get_logger("positions")


def maybe_pyramid_position(
    ticker: str,
    thesis: dict[str, Any],
    position: dict[str, Any],
    sentry: dict[str, Any] | None,
    portfolio_value: float,
    cfg: Config,
) -> dict[str, Any] | None:
    """Add to a winning position when it's working. The "ride the wave"
    operator — current behavior caps every entry at one bracket plus trail.
    Now: at +``pyramid_trigger_pct`` (5%) gain with the trailing stop active
    (so downside is bounded), we add ``pyramid_size_fraction`` (50%) of the
    original notional via a marketable LIMIT buy (a market buy is rejected as
    a wash trade while the protective stop rests on the book), capped at
    ``pyramid_max_total_pct`` of portfolio, then extend the stop to cover the
    enlarged position.

    Pyramids fire exactly once per position (tracked via
    ``trailing_state[ticker]["pyramid_added"]``). Safety preconditions:
      - pyramid_enabled in config (default True)
      - trailing stop active = gain >= trailing_trigger_pct (so any reversal
        hits the broker stop at breakeven or better)
      - sentry signal is CONTINUE (no news/price red flag)
      - thesis is still BULLISH + selected_for_trading
      - the add wouldn't push total position above the per-ticker cap

    Returns a trade record if a pyramid add fired; else None.
    """
    if not getattr(cfg.trading, "pyramid_enabled", False):
        return None

    state = _load_trailing_state()
    ts = state.get(ticker, {}) or {}
    if ts.get("pyramid_added"):
        return None

    # Same-cycle wash-trade guard: if TP1 just sold this ticker, Alpaca will
    # reject an immediate market-buy on the opposite side as a wash trade
    # ("code 40310000, potential wash trade detected"). Wait until the next
    # cycle so the partial sell settles first. The pyramid trigger persists
    # — we'll just take the add at the next executor run.
    tp1_ts_str = ts.get("tp1_timestamp")
    if tp1_ts_str:
        try:
            tp1_ts = datetime.fromisoformat(tp1_ts_str)
            age_min = (datetime.now(timezone.utc) - tp1_ts).total_seconds() / 60
            if age_min < 30:
                log.info(
                    f"Pyramid deferred for {ticker}: TP1 fired {age_min:.0f}min "
                    f"ago — avoiding wash-trade rejection. Will retry next cycle."
                )
                return None
        except (ValueError, TypeError):
            pass

    if thesis.get("thesis") != "BULLISH" or not thesis.get("selected_for_trading"):
        return None
    if sentry and sentry.get("signal") == "ABORT":
        return None

    current_price = float(position.get("current_price", 0))
    entry_price = float(position.get("avg_entry_price", 0))
    qty = float(position.get("qty", 0))
    if not current_price or not entry_price or qty <= 0:
        return None
    if _is_fractional(qty):
        return None  # Pyramid only on whole-share positions

    gain_pct = (current_price - entry_price) / entry_price
    if gain_pct < cfg.trading.pyramid_trigger_pct:
        return None

    # Require the trailing stop to be active (gain >= trailing_trigger_pct)
    # so downside on the combined position is bounded at breakeven or better.
    if gain_pct < cfg.trading.trailing_trigger_pct:
        return None

    # Compute add size: original notional × pyramid_size_fraction, but cap
    # at the per-ticker concentration limit.
    current_notional = qty * current_price
    add_notional = (qty * entry_price) * cfg.trading.pyramid_size_fraction
    cap_notional = portfolio_value * cfg.trading.pyramid_max_total_pct
    max_add_notional = max(0.0, cap_notional - current_notional)
    add_notional = min(add_notional, max_add_notional)
    if add_notional <= 0:
        log.info(
            f"Pyramid skipped for {ticker}: position already at "
            f"{current_notional / portfolio_value:.0%} of portfolio "
            f"(cap {cfg.trading.pyramid_max_total_pct:.0%})"
        )
        # Still mark pyramid_added so we don't keep computing this every cycle
        ts["pyramid_added"] = True
        ts["pyramid_skipped_reason"] = "at concentration cap"
        state[ticker] = ts
        _save_trailing_state(state)
        return None

    add_qty = int(add_notional / current_price)
    if add_qty <= 0:
        ts["pyramid_added"] = True
        state[ticker] = ts
        _save_trailing_state(state)
        return None

    log.info(
        f"PYRAMID for {ticker}: position +{gain_pct:.1%}, adding {add_qty} "
        f"shares @ ~${current_price:.2f} on top of {int(qty)} existing"
    )

    # WHY A LIMIT BUY, NOT A MARKET BUY:
    # The position is always protected by a resting sell stop. Alpaca rejects a
    # MARKET buy placed while an opposite-side stop/limit is open as a
    # "potential wash trade" (code 40310000, "use complex/limit/stop_limit
    # orders"). In production this made EVERY pyramid fail. A marketable LIMIT
    # buy is accepted alongside the resting stop, so we never have to drop the
    # protective stop to add. Price the limit slightly through the market
    # (current * 1.003) for a near-immediate fill.
    limit_price = round(current_price * 1.003, 2)
    try:
        buy_order = place_limit_buy(
            ticker, add_qty, limit_price, cfg, time_in_force="day",
        )
    except Exception as exc:
        log.error(f"Pyramid limit-buy failed for {ticker}: {exc}")
        return None

    # Wait for the add to fill before touching the stop. A marketable limit
    # fills within seconds during market hours.
    buy_id = buy_order.get("id") if isinstance(buy_order, dict) else None
    fill_status = _wait_for_order_canceled(buy_id, cfg) if buy_id else None
    if fill_status != "filled":
        # Didn't fill in the polling window (price ran away, or off-hours queue).
        # Cancel the resting add so we don't get a surprise UNPROTECTED fill
        # later — the existing stop only covers the original shares. We'll
        # retry the pyramid on a future cycle if conditions still hold.
        if buy_id:
            try:
                cancel_order(buy_id, cfg)
            except Exception as cexc:  # noqa: BLE001
                log.warning(f"Pyramid {ticker}: failed to cancel unfilled add {buy_id}: {cexc}")
        log.info(
            f"Pyramid deferred for {ticker}: add order did not fill "
            f"(status={fill_status}) — leaving existing stop in place, will retry"
        )
        return None

    # Add filled. Extend the protective stop to cover the FULL position so the
    # newly-added shares aren't left bare until the next trailing cycle. Cancel
    # the old (partial-coverage) stop and re-place one for the full qty at the
    # same protective price. Sell-to-sell cancel+replace is not a wash trade,
    # and place_native_stop_loss clamps to available qty as a backstop.
    new_total_qty = qty + add_qty
    try:
        open_orders = get_open_orders(ticker, cfg)
        existing_stop = next(
            (
                o for o in open_orders
                if o.get("type") in ("stop", "stop_limit")
                and o.get("side") == "sell"
            ),
            None,
        )
        protective_price = (
            float(existing_stop.get("stop_price", 0)) if existing_stop else 0.0
        ) or float(thesis.get("stop_loss_price") or 0) or round(entry_price * 1.005, 2)
        if existing_stop:
            cancel_order(existing_stop["id"], cfg)
            _wait_for_order_canceled(existing_stop["id"], cfg)
        place_native_stop_loss(ticker, new_total_qty, protective_price, cfg)
        log.info(
            f"Pyramid {ticker}: stop extended to {new_total_qty} shares "
            f"@ ${protective_price:.2f} (covers added {add_qty})"
        )
    except Exception as exc:  # noqa: BLE001
        # The add filled but we couldn't extend the stop. The original stop (if
        # it was never cancelled) still covers the original shares; the added
        # shares ride to the next trailing cycle, which re-places a full-qty
        # stop. Surface loudly.
        log.error(
            f"Pyramid {ticker}: add filled but stop extension to "
            f"{new_total_qty} shares failed: {exc} — added shares protected at "
            f"next trailing cycle"
        )

    try:
        from titantrade.notifier import notify_pyramid_added
        notify_pyramid_added(
            ticker=ticker, add_shares=int(add_qty), add_price=current_price,
            existing_shares=int(qty), gain_pct=gain_pct,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Pyramid Discord notify failed for {ticker}: {exc}")

    trade = _trade_record(
        ticker=ticker,
        action="BUY",
        shares=float(add_qty),
        price=current_price,
        trigger="pyramid",
        reasoning=(
            f"Pyramiding into winner: position +{gain_pct:.1%}, trailing stop "
            f"active, sentry CONTINUE, thesis still BULLISH"
        ),
    )
    _append_trade(trade)

    ts["pyramid_added"] = True
    ts["pyramid_price"] = current_price
    ts["pyramid_timestamp"] = datetime.now(timezone.utc).isoformat()
    state[ticker] = ts
    _save_trailing_state(state)
    return trade


def manage_trailing_stop(
    ticker: str,
    thesis: dict[str, Any],
    position: dict[str, Any],
    open_orders: list[dict[str, Any]],
    cfg: Config,
    stock_atr: float | None = None,
) -> None:
    """Ratchet the stop-loss upward as the position gains value, and take
    partial profit in tranches.

    Trailing distance is **ATR-based** (default 2.5 ATRs below HWM). The old
    fixed 3% trail was too tight: a position 8% in the money with normal
    intraday volatility would crystallize on noise. ATR scales with the
    ticker's actual movement.

    Tranched TP: when gain reaches ``tp1_trigger_fraction`` of the upside
    distance from entry to the thesis take-profit, sell ``tp1_fraction`` of
    the position at market and raise the stop to breakeven on the remainder.
    De-risks while keeping the runway open for outsized winners.

    Falls back to ``trailing_distance_pct`` (5%) when ATR is unavailable.
    """
    current_price = float(position.get("current_price", 0))
    entry_price = float(position.get("avg_entry_price", 0))
    qty = float(position.get("qty", 0))

    if not current_price or not entry_price or qty <= 0:
        return

    gain_pct = (current_price - entry_price) / entry_price
    trigger = cfg.trading.trailing_trigger_pct

    trailing_state = _load_trailing_state()
    ts = trailing_state.get(ticker, {})

    # Update high-water mark
    hwm = max(current_price, ts.get("high_water_mark", current_price))
    ts["high_water_mark"] = hwm
    ts["entry_price"] = entry_price

    # ---- Tranched profit-taking (TP1) ----
    # When gain reaches tp1_trigger_fraction of upside-to-TP, sell tp1_fraction
    # of the position and reset the stop to breakeven. Only fires once per
    # position (tracked via ts["tp1_taken"]).
    tp_price = thesis.get("take_profit_price")
    tp1_taken = bool(ts.get("tp1_taken", False))
    if (
        tp_price
        and not tp1_taken
        and qty >= 3
        and not _is_fractional(qty)
        and tp_price > entry_price
    ):
        tp1_trigger_price = entry_price + (tp_price - entry_price) * cfg.trading.tp1_trigger_fraction
        if current_price >= tp1_trigger_price:
            # Round-to-nearest (not floor) so a configured 0.333 actually sells
            # 1/3, not 1/3 - 1 (e.g. 30 * 0.333 = 9.99, int() = 9 instead of 10).
            tp1_qty = max(1, round(qty * cfg.trading.tp1_fraction))
            log.info(
                f"TP1 TRIGGERED for {ticker} @ ${current_price:.2f} "
                f"(trigger ${tp1_trigger_price:.2f}, entry ${entry_price:.2f}, "
                f"tp ${tp_price:.2f}) — selling {tp1_qty}/{int(qty)} shares, "
                f"raising stop to breakeven on remainder"
            )
            try:
                # Cancel OCO legs so the partial sell doesn't conflict with
                # the bracket's qty accounting. We'll re-place a fresh stop
                # below for the remaining qty.
                cancel_all_orders_for_ticker(ticker, cfg)
                # Brief wait for cancels to settle (market is open per the
                # gate above; cancels should be near-instant).
                time.sleep(2)
                sell_order = place_market_sell(ticker, tp1_qty, cfg)
                # CRITICAL: wait for the partial sell to actually FILL before
                # reading the position to size the breakeven stop. The old
                # `time.sleep(2)` then read RACED the fill — the position still
                # reported the pre-sell qty, so we requested a stop for more
                # shares than were available (403), and when the restore path
                # also used the stale qty the position was left with NO stop
                # (the production FCX bare-position bug). Polling the sell order
                # to a terminal state ('filled') removes the race; and
                # place_native_stop_loss clamps to broker-available qty as a
                # final backstop so the position is never left bare.
                sell_id = sell_order.get("id") if isinstance(sell_order, dict) else None
                if sell_id:
                    _wait_for_order_canceled(sell_id, cfg)  # terminal incl. 'filled'
                else:
                    time.sleep(2)
                new_pos = get_position(ticker, cfg)
                if new_pos:
                    remaining_qty = float(new_pos.get("qty", 0))
                    if remaining_qty > 0:
                        breakeven_stop = round(entry_price * 1.005, 2)
                        place_native_stop_loss(
                            ticker, remaining_qty, breakeven_stop, cfg,
                        )
                        log.info(
                            f"TP1 complete for {ticker}: sold {tp1_qty}, "
                            f"remaining {remaining_qty} protected by "
                            f"breakeven stop @ ${breakeven_stop:.2f}"
                        )
                        try:
                            from titantrade.notifier import notify_tp1_partial
                            tp1_gain = (current_price - entry_price) / entry_price
                            notify_tp1_partial(
                                ticker=ticker, sold_shares=int(tp1_qty),
                                sold_price=current_price,
                                remaining_shares=int(remaining_qty),
                                gain_pct=tp1_gain,
                            )
                        except Exception as exc:  # noqa: BLE001
                            log.warning(f"TP1 Discord notify failed for {ticker}: {exc}")
                ts["tp1_taken"] = True
                ts["tp1_price"] = current_price
                ts["tp1_timestamp"] = datetime.now(timezone.utc).isoformat()
                trailing_state[ticker] = ts
                _save_trailing_state(trailing_state)
                # Refresh position for the trailing-stop logic below
                position = new_pos or position
                qty = float(position.get("qty", 0)) if position else 0
                # Refresh open_orders since we cancelled+replaced
                open_orders = get_open_orders(ticker, cfg)
                if qty <= 0:
                    return
            except Exception as exc:
                log.error(f"TP1 partial sell failed for {ticker}: {exc}")
                # Restoration: size the stop off the CURRENT position, not the
                # stale pre-sell `qty`. Requesting the stale (larger) qty is
                # exactly what 403'd and stranded FCX with no stop in
                # production. Re-read the position, then lean on
                # place_native_stop_loss's available-qty clamp as a final
                # guarantee the position isn't left bare.
                try:
                    cur = get_position(ticker, cfg)
                    protect_qty = float(cur.get("qty", 0)) if cur else 0.0
                    restore_stop = (
                        thesis.get("stop_loss_price")
                        or round(entry_price * 1.005, 2)
                    )
                    if protect_qty > 0 and restore_stop:
                        place_native_stop_loss(
                            ticker, protect_qty, restore_stop, cfg,
                        )
                        log.warning(
                            f"{ticker}: restored stop on {protect_qty} shares "
                            f"after TP1 failure"
                        )
                    else:
                        log.error(
                            f"CRITICAL: {ticker} TP1 failed and no position "
                            f"qty to protect (qty={protect_qty})"
                        )
                except Exception as rexc:
                    log.error(f"CRITICAL: {ticker} stop restore failed: {rexc}")
                return

    if gain_pct < trigger:
        # Not yet triggered — save state but don't trail
        ts["trailing_active"] = False
        trailing_state[ticker] = ts
        _save_trailing_state(trailing_state)
        return

    # ---- ATR-based trailing distance ----
    # 2.5x ATR below HWM by default. Floor at 1% of HWM as a cheap sanity
    # bound for very-low-ATR names. Fall back to the fixed-pct trail when
    # ATR isn't available in the data bundle.
    if stock_atr and stock_atr > 0:
        atr_trail = stock_atr * cfg.trading.trailing_atr_multiplier
        # Sanity floor: never trail tighter than 1% of HWM (prevents absurdly
        # tight stops on ultra-low-ATR names).
        min_trail = hwm * 0.01
        trail_distance = max(atr_trail, min_trail)
        new_stop = round(hwm - trail_distance, 2)
    else:
        new_stop = round(hwm * (1 - cfg.trading.trailing_distance_pct), 2)

    # Never trail below the original thesis stop (would widen risk)
    original_stop = thesis.get("stop_loss_price", 0)
    if original_stop and new_stop < original_stop:
        new_stop = original_stop

    # Never trail below entry (lock in at least breakeven once trailing activates)
    new_stop = max(new_stop, round(entry_price * 1.005, 2))

    # Check if we need to replace the existing stop
    existing_stop_order = None
    existing_stop_price = 0.0
    for o in open_orders:
        if o.get("type") in ("stop", "stop_limit") and o.get("side") == "sell":
            existing_stop_order = o
            existing_stop_price = float(o.get("stop_price", 0))
            break

    if existing_stop_price >= new_stop:
        # Existing stop is already at or above our trailing level
        ts["trailing_active"] = True
        ts["trailing_stop_price"] = existing_stop_price
        ts["last_updated"] = datetime.now(timezone.utc).isoformat()
        trailing_state[ticker] = ts
        _save_trailing_state(trailing_state)
        return

    # Cancel old stop and place new higher one
    if existing_stop_order:
        try:
            cancel_order(existing_stop_order["id"], cfg)
        except Exception as exc:
            log.error(f"Failed to cancel stop for trailing update on {ticker}: {exc}")
            return

    # Verify position still exists after cancellation
    pos_check = get_position(ticker, cfg)
    if not pos_check:
        log.info(f"Position closed during trailing stop update for {ticker}")
        trailing_state.pop(ticker, None)
        _save_trailing_state(trailing_state)
        return

    try:
        place_native_stop_loss(ticker, qty, new_stop, cfg)
        log.info(
            f"TRAILING STOP ratcheted for {ticker}: "
            f"${existing_stop_price:.2f} -> ${new_stop:.2f} "
            f"(HWM: ${hwm:.2f}, gain: {gain_pct:.1%})"
        )
    except Exception as exc:
        log.error(f"Failed to place trailing stop for {ticker}: {exc}")
        # Re-place the old stop as fallback
        if existing_stop_price > 0:
            try:
                place_native_stop_loss(ticker, qty, existing_stop_price, cfg)
            except Exception:
                log.error(f"CRITICAL: {ticker} has no stop-loss order!")

    ts["trailing_active"] = True
    ts["trailing_stop_price"] = new_stop
    ts["last_updated"] = datetime.now(timezone.utc).isoformat()
    trailing_state[ticker] = ts
    _save_trailing_state(trailing_state)
