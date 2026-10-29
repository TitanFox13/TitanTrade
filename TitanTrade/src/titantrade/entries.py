"""New-position entries, stop-out cooldowns and
committed-cash accounting (Decisions 055/056/058/059/061/063).

An entry is a single near-market bracket: the limit just above the live mark
(so it fills, as the backtest's next-close fill assumes), the stop and the
target as fixed percentages of that entry, through all eight risk gates.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from titantrade.config import Config
from titantrade.logger import get_logger, log_decision
from titantrade.retry import fetch_with_retry
from titantrade.broker import (
    place_bracket_order, get_open_orders, _headers,
    _is_fractional, get_order, get_position, cancel_order, _wait_for_order_canceled,
    place_native_stop_loss,
)
from titantrade.market_data import get_latest_price
from titantrade.trade_state import (
    _append_trade, _append_near_miss, _trade_record, _build_trade_context,
    _build_near_miss_record,
)
from titantrade.pricing import bracket_levels_invalid, earnings_blocked, entry_levels, stop_too_tight
from titantrade.cooldown import (
    _is_in_cooldown, cooldown_override_allowed, REENTRY_COOLDOWN_HOURS,
    _record_stop_out_cooldown, cooldown_exit_price,
)
from titantrade.risk_manager import pre_trade_check

log = get_logger("entries")

# After a bracket entry fills, Alpaca leaves the bracket's stop-loss leg
# permanently in ``held`` (only the take-profit leg activates) — verified on
# the paper account for both stop and stop_limit legs. So a freshly-filled
# position is downside-unprotected until the next execute cycle's
# ``_manage_held_bullish`` heal places a standalone GTC stop. We close that
# gap by polling the just-placed entry for a fill within the cycle and, on
# fill, replacing the dead held leg with a visible GTC stop immediately.
# Most trend-aware entries are marketable and fill within a few seconds;
# slower limit fills fall through to the next-cycle heal (the backstop).
_ENTRY_FILL_POLL_SECONDS = 15.0

_ENTRY_FILL_POLL_INTERVAL = 1.0

_ORDER_TERMINAL = {
    "filled", "canceled", "cancelled", "rejected", "expired", "done_for_day",
}

def _ensure_gtc_stop_on_fill(
    ticker: str,
    parent_order: dict[str, Any] | None,
    stop_price: float,
    cfg: Config,
) -> float | None:
    """Poll a just-placed bracket entry for a fill; on fill, replace the
    unreliable ``held`` bracket stop leg with a standalone GTC stop. Returns
    the average fill price when the entry filled inside the poll window
    (the fill ledger, Decision 069), else None.

    See the module-level note on ``_ENTRY_FILL_POLL_SECONDS`` for why this is
    needed. No-op when the entry doesn't fill within the poll window — the
    next-cycle heal is the backstop. Every failure path is logged; a stop is
    always attempted via ``place_native_stop_loss`` (which clamps to broker-
    available qty) so the position is not left silently bare.
    """
    if not isinstance(parent_order, dict) or not parent_order.get("id"):
        return None
    if not stop_price or stop_price <= 0:
        return None
    parent_id = parent_order["id"]

    status = None
    od: dict[str, Any] | None = None
    waited = 0.0
    while waited < _ENTRY_FILL_POLL_SECONDS:
        od = get_order(parent_id, cfg)
        status = od.get("status") if od else None
        if status in _ORDER_TERMINAL:
            break
        time.sleep(_ENTRY_FILL_POLL_INTERVAL)
        waited += _ENTRY_FILL_POLL_INTERVAL

    if status != "filled":
        log.info(
            f"Entry for {ticker} not filled within "
            f"{int(_ENTRY_FILL_POLL_SECONDS)}s (status={status}) — bracket "
            f"left in place; next-cycle heal will establish the GTC stop "
            f"if/when it fills."
        )
        return None
    try:
        fill_price: float | None = float((od or {}).get("filled_avg_price") or 0) or None
    except (TypeError, ValueError):
        fill_price = None

    # Filled: the bracket stop leg is 'held' and won't protect. Cancel the OCO
    # legs (releasing the qty), settle, then place a visible GTC stop. The TP
    # leg is dropped here exactly as the next-cycle heal does — a weekly ADJUST
    # reinstates a TP if appropriate; the stop is the safety-critical leg.
    position = get_position(ticker, cfg)
    if not position:
        return fill_price
    qty = float(position.get("qty", 0))
    if qty <= 0 or _is_fractional(qty):
        return fill_price

    open_orders = get_open_orders(ticker, cfg)
    for o in open_orders:
        try:
            cancel_order(o["id"], cfg)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                f"Entry stop reconcile {ticker}: cancel {o.get('id')} "
                f"failed: {exc}"
            )
    for o in open_orders:
        _wait_for_order_canceled(o["id"], cfg)

    try:
        place_native_stop_loss(ticker, qty, stop_price, cfg)
        log.info(
            f"Entry for {ticker} filled — replaced held bracket stop leg with "
            f"a GTC stop on {qty} shares @ ${stop_price:.2f}"
        )
    except Exception as exc:  # noqa: BLE001
        log.error(
            f"CRITICAL: {ticker} entry filled but GTC stop placement failed: "
            f"{exc} — next-cycle heal will retry"
        )
    return fill_price


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


def record_stop_out_cooldowns(cfg: Config) -> int:
    """Detect broker-side stop-loss exits and start re-entry cooldowns (ADR 056).

    ABORT exits record a cooldown when the executor handles them — but a
    protective stop fills on Alpaca's servers with nothing of ours running,
    so the executor never "handles" the exit and the cooldown never starts.
    Production DVN: GTC stop filled at the Aug 4 open (13:34 UTC), and the
    14:15 run re-bought the ticker 42 minutes later. A protective exit is a
    protective exit — both kinds now cool down, and both share the same
    override policy (>=24h and price >= 1% above the exit, Decision 059).

    Scans recent closed orders for filled protective-stop sells (type stop /
    stop_limit) whose fill time is inside the cooldown window and records each
    as a cooldown event stamped at the FILL time — idempotent across runs
    (see ``_record_stop_out_cooldown``). The 500-order page covers weeks of
    this system's volume; a fill older than the window is ignored anyway.

    Returns the number of new cooldown records written. Never raises — a
    failed scan just means this run behaves like the pre-ADR-056 executor.
    """
    url = f"{cfg.alpaca.base_url}/v2/orders"
    # No `after` param: it filters on SUBMITTED time, and a GTC stop is often
    # submitted days before it fills. Filter on filled_at client-side instead.
    params = {"status": "closed", "limit": "500", "direction": "desc"}
    try:
        resp = fetch_with_retry("GET", url, headers=_headers(cfg), params=params)
        orders = resp.json()
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Stop-out cooldown scan failed: {exc}")
        return 0

    now = datetime.now(timezone.utc)
    recorded = 0
    for o in orders:
        if o.get("side") != "sell" or o.get("type") not in ("stop", "stop_limit"):
            continue
        if o.get("status") != "filled" or not o.get("filled_at"):
            continue
        try:
            filled_dt = datetime.fromisoformat(o["filled_at"])
            age_hours = (now - filled_dt).total_seconds() / 3600
        except (ValueError, TypeError):
            continue
        if age_hours >= REENTRY_COOLDOWN_HOURS or age_hours < 0:
            continue
        ticker = o.get("symbol", "")
        price = o.get("filled_avg_price") or o.get("stop_price") or "?"
        try:
            exit_price: float | None = float(price)
        except (TypeError, ValueError):
            exit_price = None
        if _record_stop_out_cooldown(
            ticker, o["filled_at"], f"stop-loss exit @ ${price} (broker-side fill)",
            exit_price=exit_price,
        ):
            log.info(
                f"Stop-out cooldown recorded for {ticker}: protective stop "
                f"filled {o['filled_at']} @ ${price} — re-entry suppressed "
                f"(override policy applies)"
            )
            recorded += 1
    return recorded


def handle_entry(
    item: dict[str, Any],
    *,
    portfolio_value: float,
    cash_balance: float,
    positions: list[dict[str, Any]],
    data_bundle: dict[str, Any],
    cfg: Config,
) -> dict[str, Any] | None:
    """Place a bracket for a NEW plan item after the cooldown check and all
    eight risk gates. Returns the trade record, or None when skipped."""
    ticker = item["ticker"]
    current_price = get_latest_price(ticker, cfg)

    # Re-entry cooldown after a stop-out (ADR 056/059): wait 72 h, unless 24 h
    # have passed AND the price is at least 1% above the exit.
    in_cooldown, hours_since = _is_in_cooldown(ticker)
    if in_cooldown:
        exit_price = cooldown_exit_price(ticker)
        if cooldown_override_allowed(hours_since, current_price, exit_price):
            log.warning(
                f"Cooldown OVERRIDE for {ticker}: {hours_since:.1f}h since the exit, "
                f"price ${current_price:.2f} ≥ 1% above the ${exit_price:.2f} exit. Allowing re-entry."
            )
            try:
                from titantrade.notifier import notify_cooldown_override
                notify_cooldown_override(ticker, hours_since, current_price or 0, exit_price)
            except Exception as exc:  # noqa: BLE001
                log.warning(f"Cooldown override notify failed for {ticker}: {exc}")
        else:
            log.info(
                f"Skipping {ticker} entry: in re-entry cooldown "
                f"({hours_since:.1f}h since the exit, {REENTRY_COOLDOWN_HOURS - hours_since:.1f}h remaining)"
            )
            return None

    entry_price, stop_price, target_price = entry_levels(cfg, current_price, item.get("entry_price"))
    if not entry_price:
        log.warning(f"No price for {ticker} - skipping")
        return None
    invalid = bracket_levels_invalid(entry_price, stop_price, target_price)
    if invalid:
        log.info(f"Skipping {ticker} entry: {invalid}")
        return None
    too_tight = stop_too_tight(entry_price, stop_price)
    if too_tight:
        log.info(f"Skipping {ticker} entry: {too_tight}")
        return None

    # Cash already committed to other pending buys must not be double-spent.
    committed_cash = open_buy_commitment(cfg, exclude_ticker=ticker)
    sized_item = {**item, "entry_price": entry_price, "stop_price": stop_price, "target_price": target_price}
    check = pre_trade_check(
        ticker=ticker,
        item=sized_item,
        portfolio_value=portfolio_value,
        cash_balance=cash_balance,
        positions=positions,
        earnings_blocked=earnings_blocked(ticker, data_bundle),
        cfg=cfg,
        economic_calendar=data_bundle.get("economic_calendar", []),
        correlation_matrix=data_bundle.get("correlation_matrix", {}),
        committed_cash=committed_cash,
    )
    if not check["allowed"]:
        failed = check.get("failed_gates", [])
        log.info(f"BLOCKED {ticker}: {check['reason']} (gates failed: {failed})")
        log_decision(log, "executor", ticker, f"BLOCKED: {check['reason']}", item.get("reason", ""))
        if len(failed) <= 2:
            _append_near_miss(_build_near_miss_record(
                sized_item, failed, check.get("gate_results", {}), _build_trade_context(ticker, data_bundle),
            ))
            log.info(f"NEAR MISS recorded for {ticker}: {len(failed)} gate(s) failed")
        return None
    for flag in check.get("flags", []):
        log.warning(flag)

    # Brackets need whole shares (Alpaca 422s fractional brackets).
    shares = float(int(check["shares"]))
    if shares < 1:
        log.info(f"Skipping {ticker}: sized to {check['shares']} share(s) — below 1 whole share for a bracket")
        return None

    parent = place_bracket_order(
        ticker=ticker, qty=shares, entry_limit_price=entry_price,
        stop_loss_price=stop_price, take_profit_price=target_price, cfg=cfg,
    )
    fill_price = _ensure_gtc_stop_on_fill(ticker, parent, stop_price, cfg)

    trade = _trade_record(
        ticker=ticker, action="BUY", shares=shares, price=entry_price,
        trigger="entry", reasoning=item.get("reason", ""),
        stop_price=stop_price, target_price=target_price, order_type="bracket",
        fill_price=fill_price if isinstance(fill_price, (int, float)) else None,
        dip_pct=item.get("dip_pct"), risk_flags=check.get("flags", []),
        gate_results=check.get("gate_results", {}),
        context=_build_trade_context(ticker, data_bundle),
    )
    _append_trade(trade)
    log_decision(
        log, "executor", ticker, f"BUY {shares:.0f} shares", item.get("reason", ""),
        extra={"entry": entry_price, "stop": stop_price, "target": target_price, "trigger": "entry"},
    )
    return trade


