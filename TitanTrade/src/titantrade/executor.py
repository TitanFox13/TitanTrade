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

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import time

from titantrade.config import Config, STATE_DIR, load_config
from titantrade.logger import get_logger, log_decision
from titantrade.market_context import load_stock_sectors
from titantrade.retry import HTTPError, fetch_with_retry
from titantrade.risk_manager import pre_trade_check
from titantrade.cooldown import REENTRY_COOLDOWN_HOURS, _is_in_cooldown, _record_abort_cooldown, cooldown_override_allowed
from titantrade.trailing_state import _cleanup_trailing_state, _load_trailing_state, _save_trailing_state
from titantrade.pricing import _choose_entry_price, compute_trend_regime
from titantrade.broker import (  # re-exported: preserves titantrade.executor.* patch targets
    _headers,
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
    place_bracket_order,
    place_limit_buy,
    place_limit_sell,
    place_market_buy,
    place_market_sell,
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
# State helpers
# ---------------------------------------------------------------------------

def _load(filename: str) -> dict[str, Any]:
    path = STATE_DIR / filename
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


# Cap the size of append-only state files. Older records get spilled to a
# timestamped archive next to the live file. Without this the files grow
# linearly forever — production trade_log.json was approaching MBs after a
# month of churning.
MAX_LIVE_TRADES = 500
MAX_LIVE_NEAR_MISSES = 200


def _archive_overflow(filename: str, key: str, max_keep: int) -> None:
    """If the named file's list exceeds ``max_keep``, archive the oldest
    half to ``state/archive/{filename}.YYYYMMDD-HHMMSS.json`` and write back
    only the kept tail.
    """
    path = STATE_DIR / filename
    if not path.exists():
        return
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return
    items = data.get(key, [])
    if len(items) <= max_keep:
        return

    cutoff = len(items) - max_keep
    archived, kept = items[:cutoff], items[cutoff:]
    archive_dir = STATE_DIR / "archive"
    archive_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    archive_path = archive_dir / f"{path.stem}.{stamp}.json"
    with open(archive_path, "w") as f:
        json.dump({key: archived}, f, indent=2)
    data[key] = kept
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    log.info(
        f"Archived {len(archived)} old {key} from {filename} to "
        f"{archive_path.name}"
    )


def _append_trade(trade: dict[str, Any]) -> None:
    path = STATE_DIR / "trade_log.json"
    data = _load("trade_log.json")
    data.setdefault("trades", []).append(trade)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    _archive_overflow("trade_log.json", "trades", MAX_LIVE_TRADES)


def _append_near_miss(record: dict[str, Any]) -> None:
    path = STATE_DIR / "near_misses.json"
    data = _load("near_misses.json")
    data.setdefault("near_misses", []).append(record)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    _archive_overflow("near_misses.json", "near_misses", MAX_LIVE_NEAR_MISSES)


def _build_trade_context(
    ticker: str,
    data_bundle: dict[str, Any],
    sentry: dict[str, Any] | None,
) -> dict[str, Any]:
    """Extract a snapshot of market/technical context at trade time."""
    stock_data = data_bundle.get("stocks", {}).get(ticker, {})
    market = data_bundle.get("market_context", {})
    technicals = stock_data.get("technical_indicators", {})
    earnings = stock_data.get("earnings", {})
    price_vs_sma = technicals.get("price_vs_sma", {})
    macd = technicals.get("macd", {})
    spy = market.get("spy", {})

    news = stock_data.get("news", [])
    recent_headlines = [n.get("title", "") for n in news[:3]]

    return {
        "market_regime": market.get("market_regime"),
        "vix_level": market.get("vix", {}).get("level"),
        "vix_classification": market.get("vix", {}).get("classification"),
        "spy_return_1d": spy.get("return_1d"),
        "technicals": {
            "rsi_14": technicals.get("rsi_14"),
            "macd_histogram": macd.get("histogram"),
            "atr_14": stock_data.get("atr_14"),
            "price_vs_sma_50": "above" if price_vs_sma.get("above_sma_50") else "below",
            "price_vs_sma_200": "above" if price_vs_sma.get("above_sma_200") else "below",
        },
        "sentry_signal": sentry.get("signal") if sentry else None,
        "sentry_reasoning": sentry.get("reasoning") if sentry else None,
        "recent_news": recent_headlines,
        "earnings_days_away": earnings.get("days_until_earnings"),
        "sector": stock_data.get("sector") or technicals.get("sector"),
    }


def _trade_record(
    ticker: str,
    action: str,
    shares: int,
    price: float,
    trigger: str,
    reasoning: str,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "id": f"trade_{uuid.uuid4().hex[:8]}",
        "ticker": ticker,
        "action": action,
        "shares": shares,
        "price": price,
        "total_value": round(shares * price, 2) if price else 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trigger": trigger,
        "reasoning": reasoning,
        **extra,
    }


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


# ---------------------------------------------------------------------------
# Core allocation: always-deployed SPY base + stress-state hedge swap
# ---------------------------------------------------------------------------

def manage_core_position(cfg: Config) -> dict[str, Any] | None:
    """Maintain the always-on core market exposure (and swap to hedge on stress).

    Strategic role: solve the cash-drag problem. Even when the AI thesis
    selects nothing or the gates block everything, the portfolio still
    participates in the market via this baseline allocation. Production
    pre-redesign showed 83% cash for 5+ days in a rising market; this
    is the structural fix.

    Behavior:
      - Reads ``market_health`` from sentry_signals.json.
      - If market_stress is False (default): hold ``core_ticker`` (SPY).
      - If market_stress is True: hold ``core_hedge_ticker`` (SH, inverse SPY).
      - Target value = portfolio_value * core_allocation_pct (default 30%).
      - Rebalances when current allocation drifts outside the band
        (default ±5%pts).
      - Uses market orders (we want guaranteed fill on the baseline).
      - Skipped off-hours (market orders need market open anyway).

    Returns a trade record dict if a buy/sell fired, else None.
    """
    if not is_market_open(cfg):
        log.info("Core position management deferred — market closed")
        return None

    sentry_doc = _load("sentry_signals.json")
    market_health = sentry_doc.get("market_health", {}) or {}
    stress = bool(market_health.get("market_stress", False))

    desired_ticker = cfg.trading.core_hedge_ticker if stress else cfg.trading.core_ticker
    other_ticker = cfg.trading.core_ticker if stress else cfg.trading.core_hedge_ticker

    account = get_account(cfg)
    portfolio_value = float(account.get("portfolio_value", 0))
    cash_balance = float(account.get("cash", 0))
    if portfolio_value <= 0:
        return None

    target_value = portfolio_value * cfg.trading.core_allocation_pct
    band_value = portfolio_value * cfg.trading.core_rebalance_band_pct

    positions = get_positions(cfg)
    positions_by_ticker = {p.get("symbol", ""): p for p in positions}

    # Step 1: if we're holding the "wrong" core ticker (e.g. SPY when stress
    # has flipped on), close it. The proceeds become cash that step 2 then
    # deploys into the right core ticker.
    closed_trade: dict[str, Any] | None = None
    other_pos = positions_by_ticker.get(other_ticker)
    if other_pos:
        other_qty = float(other_pos.get("qty", 0))
        if other_qty > 0:
            log.info(
                f"Core swap: closing {other_ticker} ({other_qty} shares) — "
                f"stress={stress}, switching to {desired_ticker}"
            )
            try:
                cancel_all_orders_for_ticker(other_ticker, cfg)
                close_position_at_market(other_ticker, cfg)
                closed_trade = _trade_record(
                    ticker=other_ticker,
                    action="SELL",
                    shares=other_qty,
                    price=float(other_pos.get("current_price", 0)),
                    trigger="core_swap",
                    reasoning=f"Stress={stress}, swapping core to {desired_ticker}",
                )
                _append_trade(closed_trade)
            except Exception as exc:
                log.error(f"Core swap close failed for {other_ticker}: {exc}")
                return None

    # Step 2: rebalance the desired core ticker toward target.
    desired_pos = positions_by_ticker.get(desired_ticker)
    current_value = float(desired_pos.get("market_value", 0)) if desired_pos else 0.0
    current_price = float(desired_pos.get("current_price", 0)) if desired_pos else 0.0

    if not current_price:
        # Position not yet held — fetch a price quote
        try:
            from titantrade.daily_sentry import _fetch_current_price
            current_price = _fetch_current_price(desired_ticker, cfg) or 0.0
        except Exception:
            current_price = 0.0

    if current_price <= 0:
        log.warning(f"Core: no price for {desired_ticker}, deferring rebalance")
        return closed_trade

    drift = current_value - target_value
    if abs(drift) < band_value:
        # Within the rebalance band — leave alone
        return closed_trade

    if drift < 0:
        # Under-allocated: buy more
        buy_value = -drift  # positive number
        # Don't blow through the cash floor — leave a small buffer
        from titantrade.risk_manager import MIN_CASH_RESERVE_PCT
        cash_floor = portfolio_value * (MIN_CASH_RESERVE_PCT / 100.0)
        available = max(0.0, cash_balance - cash_floor)
        buy_value = min(buy_value, available)
        if buy_value <= 0:
            log.info(
                f"Core: would buy {desired_ticker} but cash ${cash_balance:.0f} "
                f"at or below ${cash_floor:.0f} floor"
            )
            return closed_trade
        buy_qty = int(buy_value / current_price)
        if buy_qty <= 0:
            return closed_trade
        try:
            place_market_buy(desired_ticker, buy_qty, cfg)
            trade = _trade_record(
                ticker=desired_ticker,
                action="BUY",
                shares=buy_qty,
                price=current_price,
                trigger="core_rebalance",
                reasoning=(
                    f"Core rebalance: target {cfg.trading.core_allocation_pct:.0%} "
                    f"= ${target_value:.0f}, current ${current_value:.0f} "
                    f"(stress={stress})"
                ),
            )
            _append_trade(trade)
            log.info(
                f"Core BUY {desired_ticker}: {buy_qty} shares @ ${current_price:.2f} "
                f"(target ${target_value:.0f}, was ${current_value:.0f})"
            )
            try:
                from titantrade.notifier import notify_core_rebalance
                notify_core_rebalance(
                    action="BUY", ticker=desired_ticker, shares=buy_qty,
                    price=current_price, target_value=target_value,
                    current_value=current_value, stress=stress,
                )
            except Exception as exc:  # noqa: BLE001
                log.warning(f"Core BUY Discord notify failed: {exc}")
            return trade
        except Exception as exc:
            log.error(f"Core BUY failed for {desired_ticker}: {exc}")
            return closed_trade
    else:
        # Over-allocated: trim
        sell_value = drift
        sell_qty = int(sell_value / current_price)
        if sell_qty <= 0:
            return closed_trade
        try:
            place_market_sell(desired_ticker, sell_qty, cfg)
            trade = _trade_record(
                ticker=desired_ticker,
                action="SELL",
                shares=sell_qty,
                price=current_price,
                trigger="core_rebalance",
                reasoning=(
                    f"Core trim: target ${target_value:.0f}, "
                    f"current ${current_value:.0f} (stress={stress})"
                ),
            )
            _append_trade(trade)
            log.info(
                f"Core SELL {desired_ticker}: {sell_qty} shares @ ${current_price:.2f}"
            )
            return trade
        except Exception as exc:
            log.error(f"Core SELL failed for {desired_ticker}: {exc}")
            return closed_trade


def _is_core_ticker(ticker: str, cfg: Config) -> bool:
    """True if this ticker is managed by the core-allocation manager rather
    than the AI thesis path. Used to skip trailing/sentry/orphan-close logic
    on the baseline allocation.
    """
    return ticker in (cfg.trading.core_ticker, cfg.trading.core_hedge_ticker)


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


# ---------------------------------------------------------------------------
# Observability alerts (Discord)
# ---------------------------------------------------------------------------

# Bot heavily in cash for this many days triggers an alert.
STUCK_IN_CASH_PCT_THRESHOLD = 70.0
STUCK_IN_CASH_DAYS_THRESHOLD = 3

# A single ticker bought+sold this many times in this many days = churn.
TICKER_CHURN_ROUND_TRIPS = 2
TICKER_CHURN_WINDOW_DAYS = 7

# To suppress repeat alerts, we record when we last fired each one.
_ALERT_STATE_FILE = "alert_state.json"


def _load_alert_state() -> dict[str, Any]:
    return _load(_ALERT_STATE_FILE)


def _save_alert_state(data: dict[str, Any]) -> None:
    with open(STATE_DIR / _ALERT_STATE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _maybe_alert_stuck_in_cash(portfolio_value: float, cash_balance: float) -> None:
    """Discord-alert if cash % has been above threshold for N consecutive days.

    We track the date of the first observation; if we drop below the
    threshold, the tracker resets.
    """
    if portfolio_value <= 0:
        return
    cash_pct = cash_balance / portfolio_value * 100
    state = _load_alert_state()
    today = datetime.now(timezone.utc).date().isoformat()

    if cash_pct < STUCK_IN_CASH_PCT_THRESHOLD:
        # Healthy — clear any previous streak
        if "stuck_in_cash_since" in state:
            state.pop("stuck_in_cash_since", None)
            state.pop("stuck_in_cash_last_alert", None)
            _save_alert_state(state)
        return

    since = state.get("stuck_in_cash_since")
    if not since:
        state["stuck_in_cash_since"] = today
        _save_alert_state(state)
        return

    try:
        since_date = datetime.fromisoformat(since).date()
    except ValueError:
        state["stuck_in_cash_since"] = today
        _save_alert_state(state)
        return

    days = (datetime.now(timezone.utc).date() - since_date).days
    if days < STUCK_IN_CASH_DAYS_THRESHOLD:
        return

    # Don't re-alert more than once per 24h
    last_alert = state.get("stuck_in_cash_last_alert")
    if last_alert == today:
        return

    log.warning(
        f"STUCK IN CASH: {cash_pct:.0f}% cash for {days}+ days — alerting"
    )
    try:
        from titantrade.notifier import notify_stuck_in_cash
        notify_stuck_in_cash(cash_pct, days, portfolio_value)
    except Exception as exc:  # noqa: BLE001
        log.warning(f"stuck-in-cash Discord alert failed: {exc}")
    state["stuck_in_cash_last_alert"] = today
    _save_alert_state(state)


def _maybe_alert_ticker_churn() -> None:
    """Scan recent trade_log for tickers that have been bought+sold multiple
    times in a short window, indicating whipsaw.
    """
    trades = _load("trade_log.json").get("trades", [])
    if not trades:
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=TICKER_CHURN_WINDOW_DAYS)

    # Count BUY→SELL round trips per ticker in the window
    round_trips: dict[str, int] = {}
    open_buys: dict[str, int] = {}
    for t in trades:
        try:
            ts = datetime.fromisoformat(t.get("timestamp", ""))
        except (ValueError, TypeError):
            continue
        if ts < cutoff:
            continue
        sym = t.get("ticker", "")
        action = t.get("action", "")
        if action == "BUY":
            open_buys[sym] = open_buys.get(sym, 0) + 1
        elif action == "SELL" and open_buys.get(sym, 0) > 0:
            round_trips[sym] = round_trips.get(sym, 0) + 1
            open_buys[sym] -= 1

    state = _load_alert_state()
    today = datetime.now(timezone.utc).date().isoformat()
    alerts_today = state.get("churn_alerts_today", {})
    if alerts_today.get("date") != today:
        alerts_today = {"date": today, "tickers": []}

    for ticker, count in round_trips.items():
        if count < TICKER_CHURN_ROUND_TRIPS:
            continue
        if ticker in alerts_today["tickers"]:
            continue  # already alerted today
        log.warning(
            f"TICKER CHURN: {ticker} round-tripped {count}x in "
            f"{TICKER_CHURN_WINDOW_DAYS} days"
        )
        try:
            from titantrade.notifier import notify_ticker_churn
            notify_ticker_churn(ticker, count, TICKER_CHURN_WINDOW_DAYS)
        except Exception as exc:  # noqa: BLE001
            log.warning(f"ticker-churn Discord alert failed: {exc}")
        alerts_today["tickers"].append(ticker)

    state["churn_alerts_today"] = alerts_today
    _save_alert_state(state)


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
