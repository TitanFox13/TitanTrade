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

import uuid
from datetime import datetime, timezone
from typing import Any

import time

from titantrade.config import Config, load_config
from titantrade.logger import get_logger, log_decision
from titantrade.market_context import load_stock_sectors
from titantrade.retry import fetch_with_retry
from titantrade.risk_manager import pre_trade_check
from titantrade.positions import manage_trailing_stop, maybe_pyramid_position
from titantrade.core_allocation import manage_core_position
from titantrade.protection import check_gap_down_protection, close_orphaned_positions
from titantrade.trade_state import _append_near_miss, _append_trade, _build_trade_context, _load, _trade_record
from titantrade.alerts import _maybe_alert_stuck_in_cash, _maybe_alert_ticker_churn
from titantrade.cooldown import REENTRY_COOLDOWN_HOURS, _is_in_cooldown, _record_abort_cooldown, cooldown_override_allowed
from titantrade.trailing_state import _cleanup_trailing_state
from titantrade.pricing import _choose_entry_price, compute_trend_regime
from titantrade.broker import (  # re-exported: preserves titantrade.executor.* patch targets
    _headers,
    _is_fractional,
    cancel_all_orders_for_ticker,
    cancel_order,
    close_position_at_market,
    get_account,
    get_open_orders,
    get_position,
    get_positions,
    is_market_open,
    place_bracket_order,
    place_limit_buy,
    place_limit_sell,
    place_native_stop_loss,
)

log = get_logger("executor")


def open_buy_commitment(cfg: Config, exclude_ticker: str | None = None) -> float:
    """Sum the dollar notional of all open (pending, unfilled) BUY orders.

    Entry brackets are day-limit orders that don't consume cash until they
    fill, so settled ``cash`` overstates what's truly free to deploy. Feeding
    this into the cash-reserve gate (``committed_cash``) stops N simultaneously
    pending brackets from each passing the reserve check against the same cash
    and then collectively filling into margin / negative cash.

    ``exclude_ticker`` drops that symbol's pending buys from the total — used
    when re-sizing an entry for a ticker whose own prior bracket we're about to
    replace, so we don't double-count it against itself.
    """
    try:
        orders = get_open_orders(None, cfg)
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Could not read open orders for commitment calc: {exc}")
        return 0.0
    total = 0.0
    for o in orders:
        if o.get("side") != "buy":
            continue
        if exclude_ticker and o.get("symbol") == exclude_ticker:
            continue
        try:
            qty = float(o.get("qty") or 0)
            # Limit entries carry limit_price; fall back to stop/notional.
            price = float(o.get("limit_price") or o.get("stop_price") or 0)
            total += qty * price
        except (ValueError, TypeError):
            continue
    return total

# Maximum expired-bracket attempts we'll keep resubmitting before giving up.
# Raised from 5 to 20 — the prior cap was a workaround for the bigger issue
# that we were using day-TIF dip-buy limits in a rising market. Now that
# high-conviction theses fill via near-market entries (see ``_choose_entry``),
# only genuinely low-conviction ideas hit this cap, and a few extra days
# of retry isn't expensive.
MAX_BRACKET_ATTEMPTS = 20


# ---------------------------------------------------------------------------
# Main execution logic
# ---------------------------------------------------------------------------

def _handle_abort(ticker: str, sentry: dict[str, Any], cfg: Config) -> dict[str, Any] | None:
    """Cancel all orders for ticker and close position.

    Uses market sell for price-based ABORT (urgent, price already moving against us).
    Uses limit sell at 0.2% discount for news-based ABORT (less urgent, reduces slippage).
    """
    reasoning = sentry.get("reasoning", "ABORT signal")
    cancelled = cancel_all_orders_for_ticker(ticker, cfg)
    log.info(f"Cancelled {cancelled} open orders for {ticker}")

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
    _record_abort_cooldown(ticker, reasoning)
    return trade


def _handle_bullish_entry(
    ticker: str,
    thesis: dict[str, Any],
    portfolio_value: float,
    cash_balance: float,
    positions: list[dict[str, Any]],
    data_bundle: dict[str, Any],
    sentry: dict[str, Any] | None,
    cfg: Config,
) -> dict[str, Any] | None:
    """Place a bracket order for a bullish thesis, after passing ALL risk gates."""
    entry_price = thesis.get("target_entry_price")
    stop_price = thesis.get("stop_loss_price")
    take_profit_price = thesis.get("take_profit_price")
    confidence = float(thesis.get("confidence") or 0)

    if not entry_price or not stop_price:
        log.warning(f"No entry/stop price for {ticker} - skipping")
        return None

    # Fetch current price up front — used by both the cooldown override and
    # the trend-aware entry adjustment below.
    try:
        from titantrade.daily_sentry import _fetch_current_price
        current_price = _fetch_current_price(ticker, cfg)
    except Exception:
        current_price = None

    # Re-entry cooldown: don't buy back into a ticker we just ABORTed,
    # UNLESS the daily sentry confirms recovery (see cooldown_override_allowed).
    # The override prevents the production failure mode where a single-day
    # whipsaw ABORT locks us out of the recovery leg for 72 hours.
    in_cooldown, hours_since = _is_in_cooldown(ticker)
    if in_cooldown:
        if cooldown_override_allowed(
            ticker, thesis, sentry, hours_since, current_price,
        ):
            log.warning(
                f"Cooldown OVERRIDE for {ticker}: {hours_since:.1f}h since "
                f"ABORT, sentry CONTINUE + price recovered above stop. "
                f"Allowing re-entry."
            )
            try:
                from titantrade.notifier import notify_cooldown_override
                notify_cooldown_override(
                    ticker=ticker, hours_since_abort=hours_since,
                    current_price=current_price or 0,
                    stop_price=float(thesis.get("stop_loss_price") or 0),
                )
            except Exception as exc:  # noqa: BLE001
                log.warning(f"Cooldown override notify failed for {ticker}: {exc}")
        else:
            remaining = REENTRY_COOLDOWN_HOURS - hours_since
            log.info(
                f"Skipping {ticker} bullish entry: in re-entry cooldown "
                f"({hours_since:.1f}h since ABORT, {remaining:.1f}h remaining)"
            )
            return None

    # ---- Trend-aware entry adjustment ----
    # The old behavior used the thesis ``target_entry_price`` always — a
    # dip-buy below current that in a rising market simply never filled.
    # Now we look at the actual price + trend regime and adapt:
    #   - strong uptrend OR high conviction → near-market entry
    #   - uptrend → small breakout buffer above current
    #   - range → keep thesis target (capped at current to avoid paying up)
    #   - downtrend → skip (we're not bottom-fishing on day-TIF brackets)
    regime = compute_trend_regime(ticker, data_bundle, current_price)
    if regime == "down":
        log.info(
            f"Skipping {ticker} bullish entry: downtrend regime "
            f"(price below SMA-50 and SMA-200). Wait for trend reversal."
        )
        # Surface the analyst↔executor disagreement instead of skipping
        # silently. The weekly analyst keeps ranking this ticker into the
        # buy set (selected_for_trading=True, thesis=BULLISH) while the
        # technical trend gate refuses to bottom-fish it — the persistent HCA
        # case from production. Recording it as a near-miss with a synthetic
        # ``trend_regime`` gate makes the conflict visible on the dashboard so
        # a human can re-evaluate the pick (or the watchlist), rather than the
        # selection slot being burned every cycle with no trace.
        try:
            context = _build_trade_context(ticker, data_bundle, sentry)
            _append_near_miss({
                "id": f"nm_{uuid.uuid4().hex[:8]}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ticker": ticker,
                "confidence": thesis.get("confidence", 0),
                "thesis": thesis.get("thesis", ""),
                "target_entry_price": entry_price,
                "stop_loss_price": stop_price,
                "take_profit_price": take_profit_price,
                "reasoning": thesis.get("reasoning", ""),
                "failed_gates": ["trend_regime"],
                "gate_results": {
                    "trend_regime": {
                        "passed": False,
                        "detail": (
                            "Analyst-selected BULLISH but price is below both "
                            "SMA-50 and SMA-200 (downtrend) — entry gate refuses "
                            "to bottom-fish. Analyst/technical disagreement."
                        ),
                    },
                },
                "total_gates_failed": 1,
                "context": context,
            })
            log.info(f"NEAR MISS recorded for {ticker}: downtrend regime vs BULLISH selection")
        except Exception as exc:  # noqa: BLE001
            log.warning(f"Could not record downtrend near-miss for {ticker}: {exc}")
        return None

    new_entry = _choose_entry_price(thesis, current_price, regime, confidence)
    if new_entry and new_entry != entry_price:
        cur_str = f"${current_price:.2f}" if current_price else "n/a"
        log.info(
            f"Entry adapted for {ticker} ({regime}, conf {confidence:.2f}): "
            f"${entry_price:.2f} → ${new_entry:.2f} (current {cur_str})"
        )
        entry_price = new_entry
        # Recompute stop/TP to preserve risk:reward when entry moves IN EITHER
        # DIRECTION. Production bug: when entry walked DOWN (range/up regime,
        # current < target), stop stayed at thesis level and risk:reward
        # collapsed. DVN got entry $49.20→$47.16 with stop $46.74 unchanged →
        # risk = 0.9% = 0.25× ATR = guaranteed noise-stop. We now walk stop +
        # TP in either direction by the same delta as entry.
        original_target = thesis.get("target_entry_price")
        if original_target and original_target > 0 and entry_price != original_target:
            delta = entry_price - original_target  # negative if walking down
            stop_price = round(stop_price + delta, 2)
            if take_profit_price:
                take_profit_price = round(take_profit_price + delta, 2)

    # Bracket sanity check — Alpaca rejects with HTTP 422 if the math is off.
    # This happens when ADJUST has raised the stop above the original entry
    # to lock in profit on a position we already hold; that thesis is for
    # managing the position, not opening a new one.
    if stop_price >= entry_price - 0.01:
        log.info(
            f"Skipping {ticker} bullish entry: stop ${stop_price:.2f} >= "
            f"entry ${entry_price:.2f} (thesis is for managing existing "
            f"position, not new entry)"
        )
        return None
    if take_profit_price is not None and take_profit_price <= stop_price:
        log.info(
            f"Skipping {ticker} bullish entry: take_profit "
            f"${take_profit_price:.2f} <= stop ${stop_price:.2f}"
        )
        return None

    # Look up ATR from data bundle (for vol-adjusted sizing)
    stock_atr = (
        data_bundle.get("stocks", {}).get(ticker, {}).get("atr_14")
    )

    # Look up earnings block status
    earnings_blocked = (
        data_bundle.get("stocks", {}).get(ticker, {})
        .get("earnings", {}).get("is_blocked", False)
    )

    # ---- Run ALL risk gates via the risk manager ----
    economic_calendar = data_bundle.get("economic_calendar", [])
    correlation_matrix = data_bundle.get("correlation_matrix", {})
    vix_level = (
        data_bundle.get("market_context", {})
        .get("vix", {})
        .get("level")
    )

    # Cash already committed to other pending buy orders must not be
    # double-spent — keeps simultaneous entries from collectively breaching
    # the cash reserve and pushing the account into margin.
    committed_cash = open_buy_commitment(cfg, exclude_ticker=ticker)

    check = pre_trade_check(
        ticker=ticker,
        thesis=thesis,
        portfolio_value=portfolio_value,
        cash_balance=cash_balance,
        positions=positions,
        stock_atr=stock_atr,
        earnings_blocked=earnings_blocked,
        cfg=cfg,
        economic_calendar=economic_calendar,
        correlation_matrix=correlation_matrix,
        vix=vix_level,
        committed_cash=committed_cash,
    )

    if not check["allowed"]:
        failed = check.get("failed_gates", [])
        log.info(f"BLOCKED {ticker}: {check['reason']} (gates failed: {failed})")
        log_decision(
            log, "executor", ticker,
            f"BLOCKED: {check['reason']}",
            thesis.get("reasoning", ""),
        )

        # Record near-miss if blocked by 2 or fewer gates
        if len(failed) <= 2:
            context = _build_trade_context(ticker, data_bundle, sentry)
            near_miss = {
                "id": f"nm_{uuid.uuid4().hex[:8]}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ticker": ticker,
                "confidence": thesis.get("confidence", 0),
                "thesis": thesis.get("thesis", ""),
                "target_entry_price": entry_price,
                "stop_loss_price": stop_price,
                "take_profit_price": take_profit_price,
                "reasoning": thesis.get("reasoning", ""),
                "failed_gates": failed,
                "gate_results": check.get("gate_results", {}),
                "total_gates_failed": len(failed),
                "context": context,
            }
            _append_near_miss(near_miss)
            log.info(f"NEAR MISS recorded for {ticker}: {len(failed)} gate(s) failed")

        return None

    for flag in check.get("flags", []):
        log.warning(flag)

    shares = check["shares"]

    # Minimum notional check: Alpaca requires at least $1.00
    if shares * entry_price < 1.0:
        log.warning(f"Skipping {ticker}: notional ${shares * entry_price:.2f} below $1.00 minimum")
        return None

    # Two-tranche entry: 60% at target, 40% at 1.5% discount
    # Improves average entry price on dips
    if _is_fractional(shares):
        tranche1_shares = round(max(shares * 0.6, 0.01), 2)
        tranche2_shares = round(shares - tranche1_shares, 2)
    else:
        tranche1_shares = float(max(int(shares * 0.6), 1))
        tranche2_shares = shares - tranche1_shares
    tranche2_price = round(entry_price * 0.985, 2)

    if _is_fractional(tranche1_shares):
        # Fractional path: day-limit buy (no bracket support for fractional)
        # No broker-native stop — sentry price checks provide the safety net
        log.info(f"Fractional entry for {ticker}: {tranche1_shares} shares (no bracket)")
        place_limit_buy(
            ticker=ticker,
            qty=tranche1_shares,
            limit_price=entry_price,
            cfg=cfg,
            time_in_force="day",
        )
        if tranche2_shares >= 0.01:
            place_limit_buy(
                ticker=ticker,
                qty=tranche2_shares,
                limit_price=tranche2_price,
                cfg=cfg,
                time_in_force="day",
            )
    else:
        # Whole shares path: bracket orders with broker-native stops
        place_bracket_order(
            ticker=ticker,
            qty=tranche1_shares,
            entry_limit_price=entry_price,
            stop_loss_price=stop_price,
            take_profit_price=take_profit_price,
            cfg=cfg,
        )
        if tranche2_shares > 0:
            place_bracket_order(
                ticker=ticker,
                qty=tranche2_shares,
                entry_limit_price=tranche2_price,
                stop_loss_price=stop_price,
                take_profit_price=take_profit_price,
                cfg=cfg,
            )

    context = _build_trade_context(ticker, data_bundle, sentry)

    trade = _trade_record(
        ticker=ticker,
        action="BUY",
        shares=shares,
        price=entry_price,
        trigger="weekly_thesis",
        reasoning=thesis.get("reasoning", ""),
        stop_loss_price=stop_price,
        take_profit_price=take_profit_price,
        order_type="fractional_2tranche" if _is_fractional(tranche1_shares) else "bracket_2tranche",
        tranche1_shares=tranche1_shares,
        tranche2_shares=tranche2_shares,
        tranche2_price=tranche2_price,
        confidence=thesis.get("confidence", 0),
        risk_flags=check.get("flags", []),
        gate_results=check.get("gate_results", {}),
        context=context,
    )
    _append_trade(trade)
    log_decision(
        log, "executor", ticker,
        f"BUY 2-TRANCHE {tranche1_shares}+{tranche2_shares} shares",
        thesis.get("reasoning", ""),
        extra={
            "entry": entry_price,
            "tranche2": tranche2_price,
            "stop": stop_price,
            "tp": take_profit_price,
            "atr": stock_atr,
            "confidence": thesis.get("confidence", 0),
        },
    )
    return trade


def get_expired_brackets(cfg: Config) -> list[dict[str, Any]]:
    """Fetch recently expired bracket/OTO buy orders from Alpaca.

    Bracket orders use time_in_force='day', so unfilled entries expire at
    market close. This function finds them for resubmission the next morning.
    """
    url = f"{cfg.alpaca.base_url}/v2/orders"
    params = {
        "status": "closed",
        "limit": "500",
        "direction": "desc",
    }
    resp = fetch_with_retry("GET", url, headers=_headers(cfg), params=params)
    orders = resp.json()

    return [
        o for o in orders
        if o.get("status") == "expired"
        and o.get("order_class") in ("bracket", "oto")
        and o.get("side") == "buy"
    ]


def resubmit_expired_brackets(
    cfg: Config,
    thesis_doc: dict[str, Any],
    positions: list[dict[str, Any]],
    data_bundle: dict[str, Any],
) -> list[dict[str, Any]]:
    """Resubmit expired bracket orders if the thesis is still valid.

    Bracket orders use time_in_force='day' (Alpaca constraint). If the limit
    entry price wasn't hit during the trading day, the entire bracket expires.
    This function checks each expired bracket and resubmits it after re-running
    all risk gates with current portfolio values.

    Returns list of resubmitted trade records.

    Price-chase guard: if a ticker has more than ``MAX_BRACKET_ATTEMPTS``
    expired brackets accumulated in Alpaca's order history (no fills), the
    price is running away and re-submitting at ever-higher adjusted entry
    just locks in worse cost basis. Give up until next weekly review.
    """
    expired = get_expired_brackets(cfg)
    if not expired:
        return []

    log.info(f"Found {len(expired)} expired bracket orders to evaluate")

    # Count expired attempts per ticker so we can cap chase behavior.
    attempts_per_ticker: dict[str, int] = {}
    for o in expired:
        sym = o.get("symbol", "")
        attempts_per_ticker[sym] = attempts_per_ticker.get(sym, 0) + 1

    theses_by_ticker = {
        t["ticker"]: t for t in thesis_doc.get("theses", [])
    }
    held_tickers = {p["symbol"] for p in positions}

    # Load latest sentry signals so we can evaluate cooldown-override per
    # ticker without plumbing the full sentry_doc through this function.
    sentry_doc = _load("sentry_signals.json")
    sentry_by_ticker = {
        s["ticker"]: s for s in sentry_doc.get("signals", [])
    }

    account = get_account(cfg)
    portfolio_value = float(account.get("portfolio_value", 0))
    cash_balance = float(account.get("cash", 0))

    resubmitted: list[dict[str, Any]] = []

    # Expired-bracket lists are dominated by duplicate parent orders for the
    # same ticker (multiple expired BUY brackets per day, accumulated over
    # weeks). Logging a skip line per expired order produced 50–60 nearly
    # identical lines per run that drowned the actually-actionable lines.
    # We dedupe by (ticker, reason) and emit at most one line per pair,
    # appending a "(xN)" count when the same skip fired multiple times.
    _skip_seen: set[tuple[str, str]] = set()
    _skip_counts: dict[tuple[str, str], int] = {}
    # Track tickers we've already evaluated for cooldown-override this cycle.
    # The resubmit loop iterates per expired bracket (often 4+ for the same
    # ticker), and a naive implementation would re-check, re-log, re-notify
    # for each one. Production logs showed GS firing the override message
    # 4× per run with 4× Discord pings.
    _cooldown_override_seen: dict[str, bool] = {}

    def _log_skip(ticker: str, reason: str) -> None:
        key = (ticker, reason)
        if key in _skip_seen:
            _skip_counts[key] = _skip_counts.get(key, 1) + 1
            return
        _skip_seen.add(key)
        log.info(f"Skipping expired bracket for {ticker}: {reason}")

    for order in expired:
        ticker = order.get("symbol", "")
        thesis = theses_by_ticker.get(ticker)

        if not thesis:
            _log_skip(ticker, "no active thesis")
            continue

        if thesis.get("thesis") != "BULLISH" or not thesis.get("selected_for_trading"):
            _log_skip(ticker, "thesis no longer bullish/selected")
            continue

        if ticker in held_tickers:
            _log_skip(ticker, "already holding position")
            continue

        # Price-chase guard: if we've already failed to fill N times, the
        # price has clearly run away. Stop resubmitting until next weekly
        # thesis refresh, when Claude will reassess.
        attempts = attempts_per_ticker.get(ticker, 0)
        if attempts > MAX_BRACKET_ATTEMPTS:
            _log_skip(
                ticker,
                f"{attempts} prior expirations (cap {MAX_BRACKET_ATTEMPTS}) — "
                f"price chase, waiting for next weekly thesis",
            )
            continue

        # Re-entry cooldown: if we ABORTed this ticker recently, don't
        # resubmit — unless the daily sentry confirms the price has recovered
        # above the original stop and the thesis is still BULLISH.
        in_cooldown, hours_since = _is_in_cooldown(ticker)
        if in_cooldown:
            # Dedup per cycle: if we already evaluated this ticker's override
            # earlier in the resubmit loop, reuse the decision instead of
            # re-fetching the price, re-running the policy, re-logging, and
            # re-notifying. Production showed 4× per ticker per run otherwise.
            if ticker in _cooldown_override_seen:
                override_ok = _cooldown_override_seen[ticker]
            else:
                sentry_signal = sentry_by_ticker.get(ticker)
                try:
                    from titantrade.daily_sentry import _fetch_current_price
                    current_price = _fetch_current_price(ticker, cfg)
                except Exception:
                    current_price = None
                override_ok = cooldown_override_allowed(
                    ticker, thesis, sentry_signal, hours_since, current_price,
                )
                _cooldown_override_seen[ticker] = override_ok
                if override_ok:
                    log.warning(
                        f"Cooldown OVERRIDE for {ticker} (resubmit): "
                        f"{hours_since:.1f}h since ABORT, sentry CONTINUE + "
                        f"price recovered. Allowing resubmit."
                    )
                    try:
                        from titantrade.notifier import notify_cooldown_override
                        notify_cooldown_override(
                            ticker=ticker, hours_since_abort=hours_since,
                            current_price=current_price or 0,
                            stop_price=float(thesis.get("stop_loss_price") or 0),
                        )
                    except Exception as exc:  # noqa: BLE001
                        log.warning(f"Cooldown override notify failed for {ticker}: {exc}")
            if override_ok:
                pass  # Fall through to the rest of the resubmit logic
            else:
                _log_skip(
                    ticker,
                    f"in re-entry cooldown ({hours_since:.1f}h since ABORT, "
                    f"{REENTRY_COOLDOWN_HOURS - hours_since:.1f}h remaining)",
                )
                continue

        # Check for existing open orders
        open_orders = get_open_orders(ticker, cfg)
        if open_orders:
            _log_skip(ticker, "order already pending")
            continue

        original_entry = thesis.get("target_entry_price")
        original_stop = thesis.get("stop_loss_price")

        if not original_entry or not original_stop:
            continue

        # Resubmit entry uses the SAME trend-aware logic as first-entry —
        # previously this used the dip-buy ``_adjust_entry_price`` which
        # capped at current * 0.995 and silently skipped on uptrends past
        # +5%. That's why FCX was running 5+ "outside adjustment range"
        # skips per cycle in production while the price was making new highs.
        from titantrade.daily_sentry import _fetch_current_price
        current_price = _fetch_current_price(ticker, cfg)

        entry_price = original_entry
        stop_price = original_stop
        take_profit_price = thesis.get("take_profit_price")
        confidence = float(thesis.get("confidence") or 0)

        regime = compute_trend_regime(ticker, data_bundle, current_price)
        if regime == "down":
            _log_skip(ticker, "downtrend regime — wait for trend reversal")
            continue

        new_entry = _choose_entry_price(thesis, current_price, regime, confidence)
        if new_entry and new_entry != entry_price:
            log.info(
                f"Resubmit entry adapted for {ticker} ({regime}, conf {confidence:.2f}): "
                f"${entry_price:.2f} → ${new_entry:.2f}"
            )
            # Walk stop/TP in EITHER direction by the same delta to preserve
            # risk:reward. Production bug (DVN): walked entry down without
            # walking stop down → stop too tight to survive noise.
            if new_entry != original_entry:
                delta = new_entry - original_entry  # negative if walking down
                stop_price = round(stop_price + delta, 2)
                if take_profit_price:
                    take_profit_price = round(take_profit_price + delta, 2)
            entry_price = new_entry

        # Sanity-check the bracket math before sending it to the broker.
        # Alpaca requires:
        #   stop_loss.stop_price <= base_price (entry) - 0.01
        #   take_profit.limit_price > stop_loss.stop_price
        # When ADJUST raises the stop above the original entry to lock in
        # profit on a position we already hold, the (entry, stop, tp) triple
        # from the thesis becomes invalid for a NEW bracket entry. The thesis
        # is for *managing* the existing position, not *opening* a new one,
        # so skip resubmission entirely.
        if stop_price is not None and entry_price is not None:
            if stop_price >= entry_price - 0.01:
                log.info(
                    f"Skipping resubmission for {ticker}: stop ${stop_price:.2f} "
                    f">= entry ${entry_price:.2f} (thesis is for managing existing "
                    f"position, not new entry)"
                )
                continue
        if (
            take_profit_price is not None
            and stop_price is not None
            and take_profit_price <= stop_price
        ):
            log.info(
                f"Skipping resubmission for {ticker}: take_profit ${take_profit_price:.2f} "
                f"<= stop ${stop_price:.2f} (bracket math invalid)"
            )
            continue

        stock_atr = data_bundle.get("stocks", {}).get(ticker, {}).get("atr_14")
        earnings_blocked = (
            data_bundle.get("stocks", {}).get(ticker, {})
            .get("earnings", {}).get("is_blocked", False)
        )
        vix_level = (
            data_bundle.get("market_context", {}).get("vix", {}).get("level")
        )

        # Net out cash already committed to other pending buys (this ticker's
        # own expired bracket is already gone from the book, so don't exclude
        # it — but any *other* pending entry must be reserved against).
        committed_cash = open_buy_commitment(cfg, exclude_ticker=ticker)

        check = pre_trade_check(
            ticker=ticker,
            thesis=thesis,
            portfolio_value=portfolio_value,
            cash_balance=cash_balance,
            positions=positions,
            stock_atr=stock_atr,
            earnings_blocked=earnings_blocked,
            cfg=cfg,
            vix=vix_level,
            committed_cash=committed_cash,
        )

        if not check["allowed"]:
            log.info(f"Resubmission blocked for {ticker}: {check['reason']}")
            continue

        # Brackets require WHOLE shares — Alpaca rejects fractional bracket/OTO
        # orders ("fractional orders must be simple orders", HTTP 422). The
        # cash-reserve / overlay-cap reduction inside pre_trade_check can shave
        # the size down to a fraction (production: URI sized to 0.19 shares
        # when only ~$190 of investable cash remained against a ~$990 stock,
        # then the bracket 422'd). Floor here and skip cleanly if there isn't
        # room for even one whole share — resubmit again next cycle when cash
        # frees up.
        shares = float(int(check["shares"]))
        if shares < 1:
            log.info(
                f"Resubmission skipped for {ticker}: sized to "
                f"{check['shares']} share(s) — below 1 whole share for a "
                f"bracket (insufficient investable cash this cycle)"
            )
            continue

        place_bracket_order(
            ticker=ticker,
            qty=shares,
            entry_limit_price=entry_price,
            stop_loss_price=stop_price,
            take_profit_price=take_profit_price,
            cfg=cfg,
        )

        trade = _trade_record(
            ticker=ticker,
            action="BUY",
            shares=shares,
            price=entry_price,
            trigger="bracket_resubmission",
            reasoning=f"Resubmitted expired bracket: {thesis.get('reasoning', '')}",
            stop_loss_price=stop_price,
            take_profit_price=take_profit_price,
            order_type="bracket",
            confidence=thesis.get("confidence", 0),
            risk_flags=check.get("flags", []),
            gate_results=check.get("gate_results", {}),
        )
        _append_trade(trade)
        resubmitted.append(trade)

        log.info(f"Resubmitted bracket for {ticker}: {shares} shares @ ${entry_price}")

        # Refresh positions and cash for next iteration
        positions = get_positions(cfg)
        held_tickers = {p["symbol"] for p in positions}
        account = get_account(cfg)
        cash_balance = float(account.get("cash", 0))

    if resubmitted:
        log.info(f"Resubmitted {len(resubmitted)} expired brackets")

    # Summarise the deduplicated skips so the count isn't lost.
    total_extra = sum(c - 1 for c in _skip_counts.values() if c > 1)
    if total_extra > 0:
        log.info(
            f"Expired-bracket skip dedup: collapsed {total_extra} duplicate "
            f"skip line(s) across {len(_skip_counts)} (ticker, reason) pair(s)"
        )

    return resubmitted


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
                cancel_all_orders_for_ticker(ticker, cfg)
                # Wait briefly for cancels to settle before the close attempt.
                # During market hours this is near-instant; if it takes more
                # than a few seconds something is wrong and the close will
                # surface the qty-race error naturally.
                time.sleep(2)
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
                qty = float(position.get("qty", 0))
                new_stop = thesis.get("stop_loss_price")
                if new_stop and qty > 0:
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
            position = get_position(ticker, cfg)
            if not position:
                continue

            open_orders = get_open_orders(ticker, cfg)
            sell_orders = [o for o in open_orders if o.get("side") == "sell"]
            stop_orders = [
                o for o in sell_orders
                if o.get("type") in ("stop", "stop_limit")
            ]
            tp_limit_orders = [
                o for o in sell_orders if o.get("type") == "limit"
            ]
            has_stop = bool(stop_orders)

            qty = float(position.get("qty", 0))
            qty_available = float(position.get("qty_available", qty))
            fractional = _is_fractional(qty)

            if not has_stop and not fractional:
                stop_price = thesis.get("stop_loss_price")
                if stop_price:
                    # The "place a fresh stop" path is fragile in three states
                    # we keep hitting in production:
                    #   1. Market closed: a cancel-and-replace sits in
                    #      pending_cancel for hours and 403s with code 40310000.
                    #   2. A TP limit leg from the original bracket is still
                    #      active and holding all the qty (qty_available=0)
                    #      because the stop_loss leg auto-expired end-of-day
                    #      (bracket legs inherit TIF=day) but the TP didn't.
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
            elif not has_stop and fractional:
                log.info(f"Fractional position {ticker} ({qty} shares) — no broker stop (sentry protects)")

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
                            executed.append(pyramid_trade)
                except Exception as exc:
                    log.error(f"Pyramid check failed for {ticker}: {exc}")

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
