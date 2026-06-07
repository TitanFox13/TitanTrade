"""New-position entry + expired-bracket resubmission, with all 6 risk gates,
trend-aware entry adaptation, cooldown checks, and committed-cash accounting.
Extracted from executor.py (behavior-preserving).
"""

from __future__ import annotations

from typing import Any

from titantrade.config import Config
from titantrade.logger import get_logger, log_decision
from titantrade.retry import fetch_with_retry
from titantrade.broker import (
    place_bracket_order, place_limit_buy, get_open_orders, get_account,
    get_positions, _headers, _is_fractional,
)
from titantrade.trade_state import (
    _load, _append_trade, _append_near_miss, _trade_record, _build_trade_context,
    _build_near_miss_record,
)
from titantrade.pricing import (
    compute_trend_regime, adapt_entry_levels, bracket_levels_invalid,
    stock_atr, earnings_blocked, vix_level,
)
from titantrade.cooldown import (
    _is_in_cooldown, cooldown_override_allowed, REENTRY_COOLDOWN_HOURS,
)
from titantrade.risk_manager import pre_trade_check

log = get_logger("entries")


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
            _append_near_miss(_build_near_miss_record(
                ticker, thesis, entry_price, stop_price, take_profit_price,
                ["trend_regime"],
                {"trend_regime": {
                    "passed": False,
                    "detail": (
                        "Analyst-selected BULLISH but price is below both "
                        "SMA-50 and SMA-200 (downtrend) — entry gate refuses "
                        "to bottom-fish. Analyst/technical disagreement."
                    ),
                }},
                _build_trade_context(ticker, data_bundle, sentry),
            ))
            log.info(f"NEAR MISS recorded for {ticker}: downtrend regime vs BULLISH selection")
        except Exception as exc:  # noqa: BLE001
            log.warning(f"Could not record downtrend near-miss for {ticker}: {exc}")
        return None

    # Adapt entry to current price/regime, walking stop+TP to preserve R:R
    # (shared with resubmit_expired_brackets — see pricing.adapt_entry_levels).
    cur_str = f"${current_price:.2f}" if current_price else "n/a"
    prev_entry = entry_price
    entry_price, stop_price, take_profit_price, new_entry = adapt_entry_levels(
        thesis, entry_price, stop_price, take_profit_price, current_price, regime, confidence,
    )
    if new_entry is not None:
        log.info(
            f"Entry adapted for {ticker} ({regime}, conf {confidence:.2f}): "
            f"${prev_entry:.2f} → ${entry_price:.2f} (current {cur_str})"
        )

    # Bracket sanity check — Alpaca rejects invalid (entry, stop, tp) with 422.
    invalid = bracket_levels_invalid(entry_price, stop_price, take_profit_price)
    if invalid:
        log.info(f"Skipping {ticker} bullish entry: {invalid}")
        return None

    # ---- Risk-gate inputs from the data bundle ----
    atr = stock_atr(ticker, data_bundle)
    is_earnings_blocked = earnings_blocked(ticker, data_bundle)
    economic_calendar = data_bundle.get("economic_calendar", [])
    correlation_matrix = data_bundle.get("correlation_matrix", {})
    vix = vix_level(data_bundle)

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
        stock_atr=atr,
        earnings_blocked=is_earnings_blocked,
        cfg=cfg,
        economic_calendar=economic_calendar,
        correlation_matrix=correlation_matrix,
        vix=vix,
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
            _append_near_miss(_build_near_miss_record(
                ticker, thesis, entry_price, stop_price, take_profit_price,
                failed, check.get("gate_results", {}),
                _build_trade_context(ticker, data_bundle, sentry),
            ))
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

        # Adapt entry to current price/regime (shared helper — same logic the
        # first-entry path uses; walks stop+TP from the thesis target).
        prev_entry = entry_price
        entry_price, stop_price, take_profit_price, new_entry = adapt_entry_levels(
            thesis, entry_price, stop_price, take_profit_price, current_price, regime, confidence,
        )
        if new_entry is not None:
            log.info(
                f"Resubmit entry adapted for {ticker} ({regime}, conf {confidence:.2f}): "
                f"${prev_entry:.2f} → ${entry_price:.2f}"
            )

        # Skip if the (entry, stop, tp) triple is an invalid NEW bracket.
        invalid = bracket_levels_invalid(entry_price, stop_price, take_profit_price)
        if invalid:
            log.info(f"Skipping resubmission for {ticker}: {invalid}")
            continue

        atr = stock_atr(ticker, data_bundle)
        is_earnings_blocked = earnings_blocked(ticker, data_bundle)
        vix = vix_level(data_bundle)

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
            stock_atr=atr,
            earnings_blocked=is_earnings_blocked,
            cfg=cfg,
            vix=vix,
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
