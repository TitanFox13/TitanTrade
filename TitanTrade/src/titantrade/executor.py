"""Module D: Trade Executor - Alpaca API integration with proper order management.

Order strategy:
  - Entry:     Limit buy with GTC (good-till-cancelled) so it persists all week
  - Stop-loss: Native Alpaca stop order placed at broker level (fires even if bot is down)
  - Abort:     Cancel all open orders + market sell any held position immediately
  - Bracket:   Entry limit + stop-loss submitted together as an OCO bracket order

Why native stop orders matter:
  Software stop-loss (checking price in a cron job) only fires twice a day.
  A stock can drop 15% between checks. Alpaca native stops fire in real time
  regardless of whether our bot is running.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# Re-exported so the broker-resident order helpers' tests can patch
# `titantrade.executor.time.sleep` (the ADR-036 re-export patch-target
# convention). Not called directly in this module anymore.
import time  # noqa: F401

from titantrade.config import Config, load_config
from titantrade.logger import get_logger, log_decision
from titantrade.market_context import load_stock_sectors
from titantrade.entries import (
    _handle_bullish_entry, record_stop_out_cooldowns, resubmit_expired_brackets,
)
from titantrade.positions import manage_trailing_stop, maybe_pyramid_position
from titantrade.pricing import adjust_stop_too_tight
from titantrade.core_allocation import _is_core_ticker, manage_core_position
from titantrade.protection import check_gap_down_protection, close_orphaned_positions
from titantrade.trade_state import (
    _append_trade, _load, _trade_record, position_entry_stop, position_opened_after,
)
from titantrade.alerts import _maybe_alert_stuck_in_cash, _maybe_alert_ticker_churn
from titantrade.cooldown import _record_abort_cooldown
from titantrade.trailing_state import _cleanup_trailing_state
from titantrade.broker import (  # re-exported: preserves titantrade.executor.* patch targets
    _is_fractional,
    _wait_for_order_canceled,
    cancel_all_orders_for_ticker,
    cancel_order,
    close_position_at_market,
    get_account,
    get_open_orders,
    get_position,
    get_positions,
    is_market_open,
    place_limit_sell,
    place_native_stop_loss,
)

log = get_logger("executor")


# ---------------------------------------------------------------------------
# Main execution logic
# ---------------------------------------------------------------------------

def _handle_abort(ticker: str, sentry: dict[str, Any], cfg: Config) -> dict[str, Any] | None:
    """Cancel all orders for ticker and close position.

    Uses market sell for price-based ABORT (urgent, price already moving against us).
    Uses limit sell at 0.2% discount for news-based ABORT (less urgent, reduces slippage).
    """
    reasoning = sentry.get("reasoning", "ABORT signal")
    # Cancel every open order AND wait for each to reach a terminal state before
    # closing. The position's shares are held_for_orders by the protective stop;
    # closing immediately after cancelling 403s with "insufficient qty
    # (available: 0)" because the cancel hasn't released them yet (production:
    # ANET ABORT failed exactly this way during a -2.6% SPY stress day). Same
    # held-qty race the gap-down path already guards against.
    open_orders = get_open_orders(ticker, cfg)
    for order in open_orders:
        try:
            cancel_order(order["id"], cfg)
        except Exception as exc:  # noqa: BLE001
            log.warning(f"ABORT {ticker}: cancel {order.get('id')} failed: {exc}")
    for order in open_orders:
        _wait_for_order_canceled(order["id"], cfg)
    log.info(f"Cancelled {len(open_orders)} open orders for {ticker} (settled)")

    position = get_position(ticker, cfg)
    if not position:
        log.info(f"ABORT for {ticker}: no position to close")
        return None

    qty = float(position.get("qty", 0))
    if qty <= 0:
        return None

    # Price-based ABORT = urgent market sell. News-based = limit sell with small buffer.
    is_price_urgent = sentry.get("price_concern", False)
    if is_price_urgent:
        close_position_at_market(ticker, cfg)
    else:
        current = float(position.get("current_price", 0))
        if current > 0:
            limit = round(current * 0.998, 2)  # 0.2% below current — reduces slippage
            place_limit_sell(ticker, qty, limit, cfg, time_in_force="day")
        else:
            close_position_at_market(ticker, cfg)
    trade = _trade_record(
        ticker=ticker,
        action="SELL",
        shares=qty,
        price=float(position.get("current_price", 0)),
        trigger="sentry_abort",
        reasoning=reasoning,
        conflicting_headlines=sentry.get("conflicting_headlines", []),
    )
    _append_trade(trade)
    log_decision(log, "executor", ticker, "SELL (ABORT)", reasoning)
    # Suppress re-entry on this ticker until cooldown expires. Without this we
    # observed prod cycles of buy→abort→buy-higher→abort within a single week.
    # The mark we sold at anchors the override's recovery test (Decision 059).
    _record_abort_cooldown(
        ticker, reasoning, exit_price=float(position.get("current_price") or 0),
    )
    return trade


def _stop_orders(open_orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resting protective sell stops among ``open_orders``."""
    return [
        o for o in open_orders
        if o.get("side") == "sell" and o.get("type") in ("stop", "stop_limit")
    ]


def _coverage_stop_price(
    ticker: str, thesis: dict[str, Any], thesis_generated_at: str | None,
) -> float | None:
    """Stop to place when a held position has none on the book (Decision 060).

    A position opened AFTER the current review was generated (a mid-week
    re-entry, or Sunday's bracket filled on Monday) is protected at the level
    its bracket carried — the trade-log stop — because the review's level
    belongs to the position the analyst saw. Production EQIX 2026-10-02: the
    adapted bracket's $969.95 stop was replaced hours later by the thesis
    $1000 and tagged on Oct 8. Otherwise, and when the trade log has no usable
    level, the thesis stop (the analyst's current view).
    """
    if position_opened_after(ticker, thesis_generated_at):
        entry_stop = position_entry_stop(ticker)
        if entry_stop:
            return entry_stop
    return thesis.get("stop_loss_price")


def _ensure_protective_stop(
    ticker: str,
    position: dict[str, Any],
    open_orders: list[dict[str, Any]],
    stop_price: float,
    cfg: Config,
    *,
    market_open: bool,
) -> list[dict[str, Any]]:
    """Place a GTC stop at ``stop_price`` for a whole-share position that has
    no resting stop. Returns the (refreshed) open orders.

    A bracket's exit legs are DAY orders on Alpaca (the API offers no GTC
    bracket) and its stop leg is ``held`` — invisible to the open-orders
    query — while the TP leg is live, so the first run after a fill sees
    "TP leg but no stop" and the first run after the close sees nothing at
    all. Either way the position needs a GTC stop of its own.
    """
    sell_orders = [o for o in open_orders if o.get("side") == "sell"]
    tp_limit_orders = [o for o in sell_orders if o.get("type") == "limit"]
    qty = float(position.get("qty", 0))
    qty_available = float(position.get("qty_available", qty))
    # The "place a fresh stop" path is fragile in three states
    # we keep hitting in production:
    #   1. Market closed: a cancel-and-replace sits in
    #      pending_cancel for hours and 403s with code 40310000.
    #   2. A TP limit leg from the original bracket is still
    #      active and holding all the qty (qty_available=0)
    #      while the stop leg sits in ``held`` and is not
    #      returned by the open-orders query (Decision 060).
    #   3. Both 1 and 2.
    # The original code blindly tried to POST a stop and ate
    # a 403 every time. Now we detect the state and either
    # recover (market-open path) or defer cleanly (off-hours).
    held_for_orders = float(position.get("held_for_orders", 0))

    if qty_available <= 0 and tp_limit_orders:
        # TP leg is holding all the qty. We need to cancel it
        # before we can place a stop. Off-hours cancels won't
        # settle, so defer. During market hours, cancel the TP
        # and place a fresh stop (we lose the OCO link to TP,
        # but the stop is the safety-critical leg — the next
        # weekly ADJUST will reinstate a TP if appropriate).
        if not market_open:
            log.warning(
                f"{ticker} has no stop; qty held by TP leg(s) — "
                f"deferring stop placement to next market-open run"
            )
        else:
            log.warning(
                f"{ticker} has no stop; TP leg(s) hold all qty — "
                f"cancelling TP and placing fresh stop"
            )
            # Capture TP details up front so we can restore on
            # half-failure (cancel succeeded, place failed).
            # Without this, a failed place would leave the
            # position with NO exit orders at all (no stop,
            # no TP). The cost of restore is small — we just
            # re-post the same limit sell.
            tp_snapshots = [
                {
                    "qty": float(tp.get("qty", 0)),
                    "limit_price": float(tp.get("limit_price", 0)),
                }
                for tp in tp_limit_orders
                if float(tp.get("limit_price", 0)) > 0
                and float(tp.get("qty", 0)) > 0
            ]
            cancel_ok = True
            for tp in tp_limit_orders:
                try:
                    cancel_order(tp["id"], cfg)
                except Exception as cexc:
                    log.error(
                        f"Failed to cancel TP {tp.get('id')} for "
                        f"{ticker}: {cexc}"
                    )
                    cancel_ok = False
            if cancel_ok:
                try:
                    place_native_stop_loss(ticker, qty, stop_price, cfg)
                    open_orders = get_open_orders(ticker, cfg)
                except Exception as exc:
                    log.error(
                        f"Failed to place stop for {ticker} after "
                        f"TP cancel: {exc}"
                    )
                    for snap in tp_snapshots:
                        try:
                            place_limit_sell(
                                ticker,
                                snap["qty"],
                                snap["limit_price"],
                                cfg,
                                time_in_force="gtc",
                            )
                            log.warning(
                                f"{ticker}: restored TP "
                                f"{snap['qty']}@${snap['limit_price']:.2f} "
                                f"after failed stop placement"
                            )
                        except Exception as rexc:
                            log.error(
                                f"CRITICAL: {ticker} has neither "
                                f"stop nor TP — TP restore at "
                                f"${snap['limit_price']:.2f} also "
                                f"failed: {rexc}"
                            )
    elif qty_available <= 0:
        # Qty is held but not by a recognizable TP leg —
        # something unexpected. Don't blindly POST; surface
        # the discrepancy.
        log.error(
            f"{ticker} has no stop and qty_available=0 "
            f"(held_for_orders={held_for_orders}) but no TP "
            f"leg detected — manual review needed"
        )
    elif not market_open:
        log.warning(
            f"{ticker} has no stop, market closed — deferring "
            f"stop placement to next market-open run"
        )
    else:
        log.warning(
            f"No stop order found for {ticker} - placing native stop now"
        )
        try:
            place_native_stop_loss(
                ticker, qty_available, stop_price, cfg,
            )
            open_orders = get_open_orders(ticker, cfg)
        except Exception as exc:
            log.error(f"Failed to place stop for {ticker}: {exc}")
    return open_orders


def _ensure_coverage(
    ticker: str,
    thesis: dict[str, Any],
    thesis_generated_at: str | None,
    cfg: Config,
    *,
    market_open: bool,
    position: dict[str, Any],
    open_orders: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Make sure a held whole-share position carries a resting stop. No-op when
    it already does, when it is fractional-only (the sentry protects dust), or
    when no level is known. Returns the open orders, refreshed after a
    placement."""
    if open_orders is None:
        open_orders = get_open_orders(ticker, cfg)
    if _stop_orders(open_orders) or _is_fractional(float(position.get("qty", 0))):
        return open_orders
    stop_price = _coverage_stop_price(ticker, thesis, thesis_generated_at)
    if not stop_price:
        return open_orders
    return _ensure_protective_stop(
        ticker, position, open_orders, float(stop_price), cfg,
        market_open=market_open,
    )


def ensure_stop_coverage(cfg: Config) -> int:
    """Gap-check companion (Decision 060): put a GTC stop on every held
    whole-share overlay position that has none on the book.

    A bracket that fills after the pre-close run leaves DAY legs that expire
    at the close, so without this the position sits bare from the open until
    the 14:15 UTC execute run (production FCX Oct 5, EQIX Oct 12). Orphans
    (no thesis) are closed by the next execute run; the core allocation
    carries no stop by design. Returns the number of stops placed.
    """
    thesis_doc = _load("weekly_thesis.json")
    theses = {t.get("ticker"): t for t in thesis_doc.get("theses", []) or []}
    generated_at = thesis_doc.get("generated_at")
    market_open = is_market_open(cfg)
    placed = 0
    for position in get_positions(cfg):
        ticker = position.get("symbol", "")
        thesis = theses.get(ticker)
        if not thesis or _is_core_ticker(ticker, cfg):
            continue
        before = get_open_orders(ticker, cfg)
        if _stop_orders(before) or _is_fractional(float(position.get("qty", 0))):
            continue
        after = _ensure_coverage(
            ticker, thesis, generated_at, cfg,
            market_open=market_open, position=position, open_orders=before,
        )
        if _stop_orders(after):
            placed += 1
    if placed:
        log.warning(f"Stop coverage: placed {placed} missing stop(s) before the execute run")
    return placed


def _manage_held_bullish(
    ticker: str,
    thesis: dict[str, Any],
    cfg: Config,
    *,
    market_open: bool,
    data_bundle: dict[str, Any],
    sentry: dict[str, Any] | None,
    portfolio_value: float,
    thesis_generated_at: str | None = None,
) -> list[dict[str, Any]]:
    """Held BULLISH position: ensure a protective stop, ratchet the trailing
    stop, and consider pyramiding. Returns any trades produced (pyramid adds).
    Extracted from execute_trades (behavior-preserving)."""
    trades: list[dict[str, Any]] = []
    position = get_position(ticker, cfg)
    if not position:
        return trades

    open_orders = get_open_orders(ticker, cfg)
    qty = float(position.get("qty", 0))
    fractional = _is_fractional(qty)

    if fractional and not _stop_orders(open_orders):
        log.info(f"Fractional position {ticker} ({qty} shares) — no broker stop (sentry protects)")
    # Decision 060: a bare whole-share position gets its stop back here — at
    # the entry-time level when the position is newer than the review.
    open_orders = _ensure_coverage(
        ticker, thesis, thesis_generated_at, cfg,
        market_open=market_open, position=position, open_orders=open_orders,
    )

    # Trailing stop: ratchet the stop up as the position gains
    # (whole shares only). Skipped off-hours for the same reason as
    # ADJUST — the cancel would sit in pending_cancel until next open
    # and leave the position with no stop. The existing stop is on
    # the book and still protective; trailing can wait one cycle.
    if not fractional and market_open:
        # Pass ATR so the trailing distance can be volatility-adjusted
        # (2.5x ATR default) instead of a fixed % that crystallizes
        # winners on noise.
        ticker_atr = (
            data_bundle.get("stocks", {}).get(ticker, {}).get("atr_14")
        )
        try:
            manage_trailing_stop(
                ticker, thesis, position, open_orders, cfg,
                stock_atr=ticker_atr,
            )
        except Exception as exc:
            log.error(f"Trailing stop management failed for {ticker}: {exc}")

        # Pyramid into winners: adds to a position that's working
        # (+5% with trailing stop active). Runs after trailing-stop
        # management so we have the latest position state.
        try:
            refreshed_position = get_position(ticker, cfg)
            if refreshed_position:
                pyramid_trade = maybe_pyramid_position(
                    ticker, thesis, refreshed_position, sentry,
                    portfolio_value, cfg,
                )
                if pyramid_trade:
                    trades.append(pyramid_trade)
        except Exception as exc:
            log.error(f"Pyramid check failed for {ticker}: {exc}")

    return trades


def _position_live_price(position: dict[str, Any] | None) -> float | None:
    """Best available live mark for a broker position (Alpaca ``current_price``),
    or None when missing/non-numeric — callers fail open (Decision 058)."""
    if not position:
        return None
    try:
        price = float(position.get("current_price") or 0)
    except (TypeError, ValueError):
        return None
    return price if price > 0 else None


def execute_trades(cfg: Config) -> list[dict[str, Any]]:
    """Core execution: read thesis + sentry, run risk gates, place/cancel broker orders.

    Risk gates applied to every entry (constants live in risk_manager.py):
      1. Confidence threshold (>= 0.55 floor, scales sizing up to 0.95)
      2. Earnings blackout window (5 days)
      3. Drawdown circuit breaker (8% from peak)
      4. Cash reserve enforcement (5% minimum — cash is transit, not strategy)
      5. Volatility-adjusted position sizing (ATR-based, conviction-scaled
         up to MAX_POSITION_PCT = 25%)
      6. Sector exposure limit (50% max per sector)
      7. Pass 2 selection filter (only trade analyst-selected stocks)
      8. Trend regime (downtrend tickers skip entry — see compute_trend_regime)
    """
    log.info("Starting trade execution")

    # Off-hours guard. During off-hours Alpaca's cancel sits in
    # ``pending_cancel`` for hours, which makes cancel+replace patterns
    # (ADJUST, orphan close) extremely unreliable. We can still process
    # ABORT signals (those go through close_position_at_market which
    # acts on the position itself, not on the order), and we can still
    # place new bracket entries. But we'll defer ADJUST and orphan
    # close to the next market-open run. This is recorded in the cfg
    # so individual code paths can check it cheaply.
    market_open = is_market_open(cfg)
    if not market_open:
        log.info("Market is closed — ADJUST and orphan-close will defer until next open")

    # Ensure sector cache is populated for risk gate checks
    try:
        load_stock_sectors(cfg.trading.watchlist, cfg)
    except Exception as exc:
        log.warning(f"Sector cache load failed: {exc}")

    # --- Pre-flight safety checks (run before any thesis-based logic) ---

    # Close orphaned positions (expired thesis or missing thesis entry).
    # Skipped during off-hours because closing a position requires cancelling
    # its protective stop first, and that cancel will sit in ``pending_cancel``
    # for hours. The position is still safe — its old stop is on the book — and
    # the next market-hours executor run will close it cleanly.
    orphan_trades: list[dict[str, Any]] = []
    if market_open:
        try:
            orphan_trades = close_orphaned_positions(cfg)
            if orphan_trades:
                log.info(f"Closed {len(orphan_trades)} orphaned positions")
        except Exception as exc:
            log.error(f"Orphan position check failed: {exc}")
    else:
        log.info("Skipping orphan close (market closed)")

    # Gap-down protection: detect unfilled stop-limits after overnight gaps
    try:
        gap_trades = check_gap_down_protection(cfg)
        if gap_trades:
            log.info(f"Gap-down protection: closed {len(gap_trades)} positions")
    except Exception as exc:
        log.error(f"Gap-down protection failed: {exc}")
        gap_trades = []

    # --- Load thesis and proceed with normal execution ---

    thesis_doc = _load("weekly_thesis.json")
    sentry_doc = _load("sentry_signals.json")
    data_bundle = _load("data_bundle.json")

    if not thesis_doc.get("theses"):
        log.warning("No weekly thesis - skipping execution")
        return orphan_trades + gap_trades

    # Warn if thesis is overdue for review, but don't block execution
    next_review = thesis_doc.get("next_review_at", "")
    if next_review:
        try:
            review_dt = datetime.fromisoformat(next_review)
            if datetime.now(timezone.utc) > review_dt:
                log.warning("Thesis overdue for weekly review — executing with current thesis")
        except (ValueError, TypeError):
            pass

    # Warn if the data bundle (OHLCV / indicators / news baked into the
    # data_bundle.json) is stale. Several downstream decisions — trend
    # regime detection, ATR sizing, news-driven analyst review — operate
    # on this snapshot. >24h old means real numbers may have moved.
    bundle_generated = data_bundle.get("generated_at", "")
    if bundle_generated:
        try:
            bundle_ts = datetime.fromisoformat(bundle_generated)
            age_hours = (datetime.now(timezone.utc) - bundle_ts).total_seconds() / 3600
            if age_hours > 48:
                log.error(
                    f"Data bundle is {age_hours:.0f}h old — trend regime/ATR "
                    f"computations may be materially stale. Run "
                    f"`titantrade fetch` to refresh."
                )
            elif age_hours > 24:
                log.warning(
                    f"Data bundle is {age_hours:.0f}h old — consider refreshing"
                )
        except (ValueError, TypeError):
            pass

    account = get_account(cfg)
    portfolio_value = float(account.get("portfolio_value", 0))
    cash_balance = float(account.get("cash", 0))
    buying_power = float(account.get("buying_power", 0))
    log.info(
        f"Portfolio: ${portfolio_value:,.2f} | "
        f"Cash: ${cash_balance:,.2f} | "
        f"Buying power: ${buying_power:,.2f}"
    )

    positions = get_positions(cfg)

    executed: list[dict[str, Any]] = orphan_trades + gap_trades

    # Always-deployed core allocation: maintain SPY (or hedge under stress) at
    # the configured target. Solves the "83% cash in a rising market" problem
    # — the portfolio participates in the market regardless of whether the AI
    # has actionable picks.
    if market_open:
        try:
            core_trade = manage_core_position(cfg)
            if core_trade:
                executed.append(core_trade)
                positions = get_positions(cfg)
        except Exception as exc:
            log.error(f"Core position management failed: {exc}")

    # ADR 056: detect broker-side stop-loss exits and start re-entry
    # cooldowns for them. ABORT exits record a cooldown when the executor
    # handles them, but a protective stop fills on Alpaca's servers with
    # nothing of ours running — without this scan a stopped-out ticker could
    # be re-bought minutes later (DVN re-entered 42 min after its stop fired).
    # Must run BEFORE resubmission/entries so this run's decisions see the
    # cooldown. The abort-cooldown override policy still allows early
    # re-entry on confirmed recovery.
    try:
        record_stop_out_cooldowns(cfg)
    except Exception as exc:
        log.warning(f"Stop-out cooldown scan failed: {exc}")

    # Resubmit any expired bracket orders before processing new entries
    try:
        resubs = resubmit_expired_brackets(cfg, thesis_doc, positions, data_bundle)
        executed.extend(resubs)
        if resubs:
            positions = get_positions(cfg)
    except Exception as exc:
        log.error(f"Bracket resubmission failed: {exc}")

    held_tickers = {p["symbol"] for p in positions}

    sentry_signals = {
        s["ticker"]: s for s in sentry_doc.get("signals", [])
    }

    for thesis in thesis_doc["theses"]:
        ticker = thesis.get("ticker")
        if not ticker:
            log.warning(f"Thesis missing ticker field - skipping: {thesis}")
            continue
        direction = thesis.get("thesis", "NEUTRAL")
        sentry = sentry_signals.get(ticker, {})
        signal = sentry.get("signal", "CONTINUE")

        # ------------------------------------------------------------------
        # 1. ABORT: cancel all orders + market sell if holding
        # ------------------------------------------------------------------
        if signal == "ABORT":
            try:
                trade = _handle_abort(ticker, sentry, cfg)
                if trade:
                    executed.append(trade)
            except Exception as exc:
                log.error(f"ABORT handling failed for {ticker}: {exc}")
            continue

        # ------------------------------------------------------------------
        # 2. BULLISH + CONTINUE + not holding + selected by Pass 2
        # ------------------------------------------------------------------
        if direction == "BULLISH" and ticker not in held_tickers:
            # Gate: only trade stocks selected by the Pass 2 portfolio ranking
            if not thesis.get("selected_for_trading", False):
                log.info(f"Skipping {ticker}: not selected by portfolio ranking (Pass 2)")
                continue

            # Check we don't already have a pending order for this ticker
            open_orders = get_open_orders(ticker, cfg)
            if open_orders:
                log.info(f"Order already pending for {ticker} - skipping new entry")
                continue

            try:
                trade = _handle_bullish_entry(
                    ticker=ticker,
                    thesis=thesis,
                    portfolio_value=portfolio_value,
                    cash_balance=cash_balance,
                    positions=positions,
                    data_bundle=data_bundle,
                    sentry=sentry or None,
                    cfg=cfg,
                )
                if trade:
                    executed.append(trade)
                    # Refresh positions list for sector exposure checks
                    positions = get_positions(cfg)
                    # Decision 058: refresh cash too. A bracket that fills
                    # instantly (production ANET 2026-09-21) is no longer an
                    # *open* order, so open_buy_commitment() can't see it and
                    # the next ticker in this same run would be sized against
                    # pre-fill cash (DXCM was: 5% reserve → 2.6% cash).
                    # resubmit_expired_brackets already refreshes per entry.
                    account = get_account(cfg)
                    portfolio_value = float(account.get("portfolio_value", portfolio_value))
                    cash_balance = float(account.get("cash", cash_balance))
            except Exception as exc:
                log.error(f"Bullish entry failed for {ticker}: {exc}")

        # ------------------------------------------------------------------
        # 3. BEARISH + holding = exit (thesis flipped since entry)
        # ------------------------------------------------------------------
        # IMPORTANT: ADJUST review_action takes precedence. Production case:
        # FANG had thesis=BEARISH but review_action=ADJUST (analyst wanted to
        # tighten the stop, NOT exit at market). The old code fired the
        # bearish exit anyway, contradicting the analyst's intent. Now we
        # let section 4a (ADJUST) handle it — section 3 is for true thesis
        # flips where the analyst wants out, not for stop-tightening events.
        elif (
            direction == "BEARISH"
            and ticker in held_tickers
            and thesis.get("review_action") != "ADJUST"
        ):
            # Off-hours guard: cancel_all + close_position_at_market is the
            # same pending_cancel → qty-race pattern that ADJUST and orphan-
            # close already gate. Without this, the cancel sits in
            # pending_cancel and the close fails with code 40310000
            # ("insufficient qty available"). Production showed DVN and FANG
            # failing exactly this way during the Sunday-night executor run.
            # The position is still protected by its existing stop on the
            # book — deferring to the next market-hours run is safe.
            if not market_open:
                log.info(
                    f"BEARISH exit for {ticker} deferred — market closed. "
                    f"Existing stop remains active. Will retry at next "
                    f"market-hours run."
                )
                continue

            log.info(f"Thesis flipped BEARISH for {ticker} - closing position")
            # Capture the existing stop BEFORE we cancel it. If the close
            # fails (qty race, network blip, etc.), we restore the stop so
            # the position isn't left naked while we wait for the next run.
            existing_stop_price = 0.0
            open_orders_pre: list[dict[str, Any]] = []
            try:
                open_orders_pre = get_open_orders(ticker, cfg)
                existing_stop = next(
                    (
                        o for o in open_orders_pre
                        if o.get("type") in ("stop", "stop_limit")
                        and o.get("side") == "sell"
                    ),
                    None,
                )
                if existing_stop:
                    existing_stop_price = float(existing_stop.get("stop_price", 0))
            except Exception as exc:  # noqa: BLE001
                log.warning(f"Could not read existing stop for {ticker}: {exc}")

            try:
                # Cancel every resting order and wait for each to reach a
                # terminal state before closing. A blind sleep(2) is not
                # enough: Alpaca's pending_cancel can take 5-15s to settle
                # even during market hours (ADR 042), and the close then 403s
                # with code 40310000 ("insufficient qty") because the just-
                # cancelled stop still holds the shares. This is the same
                # cancel-settle pattern _handle_abort and gap-down use (ADR 037).
                for order in open_orders_pre:
                    try:
                        cancel_order(order["id"], cfg)
                    except Exception as cexc:  # noqa: BLE001
                        log.warning(
                            f"Bearish exit {ticker}: cancel "
                            f"{order.get('id')} failed: {cexc}"
                        )
                for order in open_orders_pre:
                    _wait_for_order_canceled(order["id"], cfg)
                position = get_position(ticker, cfg)
                if position:
                    qty = float(position.get("qty", 0))
                    close_position_at_market(ticker, cfg)
                    trade = _trade_record(
                        ticker=ticker,
                        action="SELL",
                        shares=qty,
                        price=float(position.get("current_price", 0)),
                        trigger="thesis_bearish",
                        reasoning=thesis.get("reasoning", "Thesis flipped bearish"),
                    )
                    _append_trade(trade)
                    executed.append(trade)
            except Exception as exc:
                log.error(f"Bearish exit failed for {ticker}: {exc}")
                # Safety net: re-place the stop we cancelled so the position
                # isn't naked while we wait for the next run.
                if existing_stop_price > 0:
                    pos_check = get_position(ticker, cfg)
                    if pos_check:
                        qty_to_protect = float(pos_check.get("qty", 0))
                        if qty_to_protect > 0:
                            try:
                                place_native_stop_loss(
                                    ticker, qty_to_protect, existing_stop_price, cfg,
                                )
                                log.warning(
                                    f"BEARISH exit failed for {ticker} — restored "
                                    f"stop @ ${existing_stop_price:.2f} to keep "
                                    f"position protected"
                                )
                            except Exception as restore_exc:
                                log.error(
                                    f"CRITICAL: {ticker} bearish exit failed AND "
                                    f"stop restore also failed: {restore_exc}. "
                                    f"Position is NAKED until next run."
                                )

        # ------------------------------------------------------------------
        # 4a. ADJUST review action: update stop/TP levels for held position
        # ------------------------------------------------------------------
        review_action = thesis.get("review_action", "NEW")
        if review_action == "ADJUST" and ticker in held_tickers:
            position = get_position(ticker, cfg)
            if position:
                # ADR 056: the ADJUST levels were computed for the position
                # the analyst reviewed on Sunday. If the ticker exited and was
                # RE-ENTERED since the review was generated, those levels
                # belong to a position that no longer exists — production DVN
                # was stopped out at the Aug 4 open, re-entered 42 min later
                # at $43.65, and the stale $43.50 ADJUST stop (set for the old
                # basis) was re-applied 0.34% below the fresh entry and tagged
                # it out the next morning. Keep the entry-time stop; next
                # Sunday's review re-syncs the levels.
                if position_opened_after(ticker, thesis_doc.get("generated_at")):
                    log.info(
                        f"ADJUST {ticker}: position was re-opened after the "
                        f"weekly review was generated — its levels don't apply "
                        f"to this position. Keeping the entry-time stop."
                    )
                    # Decision 060: still make sure that level is ON the book.
                    # The re-opened position's bracket legs are DAY orders and
                    # die at the close — production FCX sat without a stop
                    # from Fri Oct 2 20:00 to Mon Oct 5 14:15 UTC because
                    # this branch skipped every check.
                    _ensure_coverage(
                        ticker, thesis, thesis_doc.get("generated_at"), cfg,
                        market_open=market_open, position=position,
                    )
                    continue
                qty = float(position.get("qty", 0))
                new_stop = thesis.get("stop_loss_price")
                if new_stop and 0 < qty < 1:
                    # Sub-1-share dust (e.g. a TP1/partial-exit remainder):
                    # Alpaca can't place a stop on a fractional-only position,
                    # so cancel+replace would just 422 every run (the JPM/ANET
                    # daily "fractional orders must be DAY orders" error). The
                    # remainder is too small to protect — skip it.
                    log.info(
                        f"ADJUST {ticker}: {qty} share(s) of dust — no stop "
                        f"possible on a fractional-only remainder; skipping"
                    )
                elif new_stop and qty >= 1:
                    # Idempotency: if an existing stop is already at the target
                    # price, don't cancel+replace. Running cancel→place on every
                    # executor tick churns the broker and hits qty-race 403s
                    # (Alpaca's qty_available lags a few hundred ms after cancel).
                    open_orders = get_open_orders(ticker, cfg)
                    existing_stop = next(
                        (
                            o for o in open_orders
                            if o.get("type") in ("stop", "stop_limit")
                            and o.get("side") == "sell"
                        ),
                        None,
                    )
                    if existing_stop:
                        existing_price = float(existing_stop.get("stop_price", 0))
                        if abs(existing_price - new_stop) < 0.01:
                            log.info(
                                f"ADJUST {ticker}: stop already at ${new_stop:.2f} "
                                f"— skipping cancel+replace"
                            )
                            continue

                    # Off-hours guard: cancels can sit in pending_cancel for
                    # hours when the market is closed. The OLD stop (if any)
                    # is still active on the book protecting the position,
                    # so deferring the price update until the next market-
                    # hours run is safe. We defer unconditionally — even when
                    # no existing stop is found — because the fresh-place path
                    # also cancels any TP leg holding the qty, which would
                    # hang off-hours and 403.
                    if not market_open:
                        if existing_stop is not None:
                            log.info(
                                f"ADJUST {ticker}: market closed — deferring stop "
                                f"update from ${existing_price:.2f} to "
                                f"${new_stop:.2f} until next market-open run"
                            )
                        else:
                            log.info(
                                f"ADJUST {ticker}: market closed and no existing "
                                f"stop — deferring fresh stop placement to "
                                f"${new_stop:.2f} until next market-open run"
                            )
                        continue

                    # Decision 058: the analyst's level was computed against
                    # Friday's close; this run applies it ~45 min into the
                    # session, after any gap. A stop at/inside noise distance
                    # of the LIVE price is a market exit, not a stop —
                    # production ANET 2026-09-14 (raise $181 → $191, opened
                    # $189.82, filled the same second, +8% within a week).
                    # Same 1.5% floor as Decision 055, measured from the live
                    # mark. When an existing stop protects the position we
                    # keep it; with no stop at all we still place the analyst's
                    # level — unprotected is worse than tight. Fails open when
                    # the broker position carries no usable price.
                    live_price = _position_live_price(position)
                    too_tight = adjust_stop_too_tight(live_price, float(new_stop))
                    if too_tight and existing_stop is not None:
                        log.warning(
                            f"ADJUST {ticker}: NOT applying analyst stop — {too_tight}. "
                            f"Keeping existing stop @ ${existing_price:.2f}"
                        )
                        continue
                    if too_tight:
                        log.warning(
                            f"ADJUST {ticker}: {too_tight} — but the position has "
                            f"no stop at all, placing it anyway"
                        )

                    # Remember the old stop price so we can restore it if the
                    # cancel+replace half-fails (cancel succeeded, place failed).
                    # Without this safety net, ADJUST could strand a position
                    # with no stop-loss at all.
                    old_stop_price = (
                        float(existing_stop.get("stop_price", 0))
                        if existing_stop else 0.0
                    )

                    log.info(f"ADJUST: Replacing stop for {ticker} to ${new_stop:.2f}")
                    try:
                        cancel_all_orders_for_ticker(ticker, cfg)
                        place_native_stop_loss(ticker, qty, new_stop, cfg)
                    except Exception as exc:
                        log.error(f"Failed to adjust stop for {ticker}: {exc}")
                        if old_stop_price > 0:
                            log.warning(
                                f"ADJUST {ticker}: restoring old stop @ ${old_stop_price:.2f} "
                                f"so position is not left unprotected"
                            )
                            try:
                                place_native_stop_loss(ticker, qty, old_stop_price, cfg)
                            except Exception as restore_exc:
                                log.error(
                                    f"CRITICAL: {ticker} has no stop-loss order — "
                                    f"old-stop restore also failed: {restore_exc}"
                                )
            continue

        # ------------------------------------------------------------------
        # 4b. Holding a BULLISH position: ensure stop-loss + trailing stop
        # ------------------------------------------------------------------
        elif direction == "BULLISH" and ticker in held_tickers:
            executed.extend(_manage_held_bullish(
                ticker, thesis, cfg, market_open=market_open,
                data_bundle=data_bundle, sentry=sentry,
                portfolio_value=portfolio_value,
                thesis_generated_at=thesis_doc.get("generated_at"),
            ))
    # Clean up trailing state for tickers no longer held
    try:
        final_positions = get_positions(cfg)
        _cleanup_trailing_state({p["symbol"] for p in final_positions})
    except Exception:
        pass

    # Post-run observability alerts (best-effort; never let them break exec)
    try:
        _maybe_alert_stuck_in_cash(portfolio_value, cash_balance)
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Stuck-in-cash check failed: {exc}")
    try:
        _maybe_alert_ticker_churn()
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Ticker-churn check failed: {exc}")

    log.info(f"Execution complete: {len(executed)} actions taken")
    return executed


def main() -> None:
    cfg = load_config()

    if cfg.trading.trading_mode == "live":
        log.warning("=== LIVE TRADING MODE ===")
    else:
        log.info("Paper trading mode")

    trades = execute_trades(cfg)
    for t in trades:
        price_str = f"${t.get('price', 0):.2f}" if t.get('price') else "market"
        print(f"  {t['action']:4} {t.get('shares', '?'):>5} {t['ticker']:<6} @ {price_str}  [{t['trigger']}]")


if __name__ == "__main__":
    main()
