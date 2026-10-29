"""Execution orchestrator (Decisions 036, 060, 061, 063).

``execute_trades`` runs, in order:
  1. pre-flight — orphan close (held names without a plan item), gap-down protection
  2. plan + data bundle
  3. core — SPY to its residual target, freeing the cash this run's entries
     need, then the momentum ETF to its sleeve target (Decision 068)
  4. stop-out cooldown scan
  5. NEW items → entries through the gates; HOLD items → stop coverage,
     then the target or the holding limit closes the position
  6. observability alerts

Broker calls go through ``broker``; the names re-exported below are what
tests patch (``titantrade.executor.<name>``).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from titantrade.config import Config, load_config
from titantrade.logger import get_logger
from titantrade.broker import (  # re-exported: patch targets
    _is_fractional,
    cancel_all_orders_for_ticker,
    cancel_order,
    get_account,
    get_open_orders,
    get_position,
    get_positions,
    is_market_open,
    place_limit_sell,
    place_native_stop_loss,
)
from titantrade.market_context import load_stock_sectors
from titantrade.protection import check_gap_down_protection, close_orphaned_positions, close_position_settled
from titantrade.entries import handle_entry, record_stop_out_cooldowns
from titantrade.core_allocation import _is_core_ticker, manage_core_position
from titantrade.mechanical import cash_target_pct, core_target_pct, momentum_target_pct
from titantrade.signals import trading_days_between
from titantrade.trade_state import _load, _save, position_opened_at
from titantrade.alerts import _maybe_alert_stuck_in_cash, _maybe_alert_ticker_churn

log = get_logger("executor")

__all__ = [
    "execute_trades", "ensure_stop_coverage", "check_gap_down_protection",
    "close_orphaned_positions", "get_positions",
    "get_account", "is_market_open", "cancel_all_orders_for_ticker",
]


# ---------------------------------------------------------------------------
# Stop coverage (Decision 060)
# ---------------------------------------------------------------------------

def _stop_orders(open_orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resting protective sell stops among ``open_orders``."""
    return [
        o for o in open_orders
        if o.get("side") == "sell" and o.get("type") in ("stop", "stop_limit")
    ]


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
    all. Either way the position needs a GTC stop of its own. Three states:
      1. market closed: a cancel sits in pending_cancel for hours → defer
      2. a TP limit leg holds all the qty (qty_available = 0) → cancel it,
         place the stop; on a failed placement re-post the TP so the
         position is never left with no exit order at all
      3. no orders at all → place the stop
    """
    sell_orders = [o for o in open_orders if o.get("side") == "sell"]
    tp_limit_orders = [o for o in sell_orders if o.get("type") == "limit"]
    qty = float(position.get("qty", 0))
    qty_available = float(position.get("qty_available", qty))
    held_for_orders = float(position.get("held_for_orders", 0))

    if qty_available <= 0 and tp_limit_orders:
        if not market_open:
            log.warning(f"{ticker} has no stop; qty held by TP leg(s) — deferring stop placement to next market-open run")
            return open_orders
        log.warning(f"{ticker} has no stop; TP leg(s) hold all qty — cancelling TP and placing fresh stop")
        tp_snapshots = [
            {"qty": float(tp.get("qty", 0)), "limit_price": float(tp.get("limit_price", 0))}
            for tp in tp_limit_orders
            if float(tp.get("limit_price", 0)) > 0 and float(tp.get("qty", 0)) > 0
        ]
        cancel_ok = True
        for tp in tp_limit_orders:
            try:
                cancel_order(tp["id"], cfg)
            except Exception as cexc:  # noqa: BLE001
                log.error(f"Failed to cancel TP {tp.get('id')} for {ticker}: {cexc}")
                cancel_ok = False
        if cancel_ok:
            try:
                place_native_stop_loss(ticker, qty, stop_price, cfg)
                open_orders = get_open_orders(ticker, cfg)
            except Exception as exc:  # noqa: BLE001
                log.error(f"Failed to place stop for {ticker} after TP cancel: {exc}")
                for snap in tp_snapshots:
                    try:
                        place_limit_sell(ticker, snap["qty"], snap["limit_price"], cfg, time_in_force="gtc")
                        log.warning(f"{ticker}: restored TP {snap['qty']}@${snap['limit_price']:.2f} after failed stop placement")
                    except Exception as rexc:  # noqa: BLE001
                        log.error(f"CRITICAL: {ticker} has neither stop nor TP — TP restore at ${snap['limit_price']:.2f} also failed: {rexc}")
    elif qty_available <= 0:
        log.error(
            f"{ticker} has no stop and qty_available=0 (held_for_orders={held_for_orders}) "
            f"but no TP leg detected — manual review needed"
        )
    elif not market_open:
        log.warning(f"{ticker} has no stop, market closed — deferring stop placement to next market-open run")
    else:
        log.warning(f"No stop order found for {ticker} - placing native stop now")
        try:
            place_native_stop_loss(ticker, qty_available, stop_price, cfg)
            open_orders = get_open_orders(ticker, cfg)
        except Exception as exc:  # noqa: BLE001
            log.error(f"Failed to place stop for {ticker}: {exc}")
    return open_orders


def _ensure_coverage(
    ticker: str,
    stop_price: float | None,
    cfg: Config,
    *,
    market_open: bool,
    position: dict[str, Any],
    open_orders: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Make sure a held whole-share position carries a resting stop at the
    plan's level. No-op when it already does, when it is fractional-only
    (dust) or when no level is known."""
    if open_orders is None:
        open_orders = get_open_orders(ticker, cfg)
    if _stop_orders(open_orders) or _is_fractional(float(position.get("qty", 0))) or not stop_price:
        return open_orders
    return _ensure_protective_stop(
        ticker, position, open_orders, float(stop_price), cfg, market_open=market_open,
    )


def ensure_stop_coverage(cfg: Config) -> int:
    """Gap-check companion: put a GTC stop on every held plan position that
    has none on the book (a bracket that fills after the pre-close run leaves
    DAY legs that expire at the close). Returns the number of stops placed."""
    plan = _load("plan.json")
    stops = {i.get("ticker"): i.get("stop_price") for i in plan.get("items", []) if i.get("action") == "HOLD"}
    market_open = is_market_open(cfg)
    placed = 0
    for position in get_positions(cfg):
        ticker = position.get("symbol", "")
        if ticker not in stops or _is_core_ticker(ticker, cfg):
            continue
        before = get_open_orders(ticker, cfg)
        if _stop_orders(before) or _is_fractional(float(position.get("qty", 0))):
            continue
        after = _ensure_coverage(ticker, stops[ticker], cfg, market_open=market_open, position=position, open_orders=before)
        if _stop_orders(after):
            placed += 1
    if placed:
        log.warning(f"Stop coverage: placed {placed} missing stop(s) before the execute run")
    return placed


# ---------------------------------------------------------------------------
# Held positions: coverage, then target / holding-limit exits
# ---------------------------------------------------------------------------

def _manage_held(item: dict[str, Any], cfg: Config, *, market_open: bool) -> list[dict[str, Any]]:
    """Keep the stop on the book, then exit at the target or after the holding
    limit — evaluated at the executor runs, close-based as backtested. The
    stop, the target and the clock are the only exits."""
    ticker = item["ticker"]
    position = get_position(ticker, cfg)
    if not position:
        return []
    _ensure_coverage(ticker, item.get("stop_price"), cfg, market_open=market_open, position=position)
    if not market_open:
        return []
    qty = float(position.get("qty") or 0)
    if qty <= 0:
        return []
    try:
        plpc = float(position.get("unrealized_plpc") or 0)
    except (TypeError, ValueError):
        plpc = 0.0
    days = trading_days_between(position_opened_at(ticker))
    if plpc >= cfg.trading.tp_pct:
        trigger, reason = "target", f"{plpc:+.1%} reached the +{cfg.trading.tp_pct:.0%} target after {days} trading days"
    elif days >= cfg.trading.max_hold_days:
        trigger, reason = "holding_limit", f"{days} trading days held (limit {cfg.trading.max_hold_days}) at {plpc:+.1%}"
    else:
        return []
    log.info(f"Exit for {ticker}: {reason}")
    trade = close_position_settled(ticker, cfg, trigger=trigger, reason=reason)
    return [trade] if trade else []


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------

def execute_trades(cfg: Config) -> list[dict[str, Any]]:
    """One executor run; returns the trade records it produced."""
    log.info("Starting trade execution")
    market_open = is_market_open(cfg)
    if not market_open:
        log.info("Market is closed — core, orphan close and exits defer until the next open")

    try:
        load_stock_sectors(cfg.trading.watchlist, cfg)
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Sector cache load failed: {exc}")

    # --- Pre-flight safety ---
    executed: list[dict[str, Any]] = []
    if market_open:
        try:
            orphan_trades = close_orphaned_positions(cfg)
            if orphan_trades:
                log.info(f"Closed {len(orphan_trades)} orphaned positions")
            executed.extend(orphan_trades)
        except Exception as exc:  # noqa: BLE001
            log.error(f"Orphan position check failed: {exc}")
    try:
        gap_trades = check_gap_down_protection(cfg)
        if gap_trades:
            log.info(f"Gap-down protection: closed {len(gap_trades)} positions")
        executed.extend(gap_trades)
    except Exception as exc:  # noqa: BLE001
        log.error(f"Gap-down protection failed: {exc}")

    # --- Plan + bundle ---
    plan = _load("plan.json")
    data_bundle = _load("data_bundle.json")
    items = plan.get("items", []) or []
    if not items and not plan.get("watch"):
        log.warning("No plan — run `titantrade signals` first; skipping execution")
        return executed
    bundle_generated = data_bundle.get("generated_at", "")
    if bundle_generated:
        try:
            age_hours = (datetime.now(timezone.utc) - datetime.fromisoformat(bundle_generated)).total_seconds() / 3600
            if age_hours > 48:
                log.error(f"Data bundle is {age_hours:.0f}h old — run `titantrade fetch`")
            elif age_hours > 24:
                log.warning(f"Data bundle is {age_hours:.0f}h old — consider refreshing")
        except (ValueError, TypeError):
            pass

    account = get_account(cfg)
    portfolio_value = float(account.get("portfolio_value", 0))
    cash_balance = float(account.get("cash", 0))
    log.info(f"Portfolio: ${portfolio_value:,.2f} | Cash: ${cash_balance:,.2f} | Buying power: ${float(account.get('buying_power', 0)):,.2f}")
    positions = get_positions(cfg)

    # --- Core: SPY is the residual (Decision 061) ---
    held_now = {p.get("symbol") for p in positions}
    planned = sum(1 for i in items if i.get("action") == "NEW" and i.get("ticker") not in held_now)
    scale = plan.get("exposure_scale")
    if scale is None:   # a plan from before Decision 068
        scale = (plan.get("insurance", {}) or {}).get("exposure_scale") or 1.0
    scale = float(scale)
    core_target = core_target_pct(cfg, portfolio_value, positions, planned_new_slots=planned, exposure_scale=scale)
    sleeve = cfg.trading.momentum_ticker
    sleeve_target = momentum_target_pct(cfg, scale) if (cfg.trading.momentum_weight > 0 or sleeve in held_now) else None
    log.info(
        f"Core target {core_target:.0%} of equity (planned new slots {planned}, exposure scale {scale})"
        + (f" | {sleeve} target {sleeve_target:.0%}" if sleeve_target is not None else "")
    )
    if market_open:
        legs = [(cfg.trading.core_ticker, core_target)]
        if sleeve_target is not None:
            legs.append((sleeve, sleeve_target))   # SPY first: its sale funds the sleeve and the entries
        cash_leg = cfg.trading.cash_ticker
        if cash_leg and (scale < 1 or cash_leg in held_now):
            # The T-bill leg (071): sells first when the idle share shrinks (its cash funds the
            # re-risking buys), buys last when it grows (with what the other legs' sales freed).
            cash_target = cash_target_pct(cfg, scale)
            cash_now = sum(float(p.get("market_value") or 0) for p in positions if p.get("symbol") == cash_leg) / portfolio_value if portfolio_value else 0.0
            legs.insert(0, (cash_leg, cash_target)) if cash_now > cash_target else legs.append((cash_leg, cash_target))
            log.info(f"{cash_leg} target {cash_target:.0%} of equity (idle capital), now {cash_now:.0%}")
        for leg, target in legs:
            try:
                core_trade = manage_core_position(cfg, target_pct=target, ticker=leg)
                if core_trade:
                    executed.append(core_trade)
                    positions = get_positions(cfg)
                    account = get_account(cfg)   # the core trade moved cash
                    portfolio_value = float(account.get("portfolio_value", portfolio_value))
                    cash_balance = float(account.get("cash", cash_balance))
            except Exception as exc:  # noqa: BLE001
                log.error(f"Core position management failed for {leg}: {exc}")

    # --- Stop-out cooldowns (ADR 056) before anything can re-enter ---
    try:
        record_stop_out_cooldowns(cfg)
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Stop-out cooldown scan failed: {exc}")

    held_tickers = {p["symbol"] for p in positions}

    # --- Items ---
    for item in items:
        ticker = item.get("ticker")
        action = item.get("action")
        if not ticker:
            continue
        if action == "NEW" and ticker not in held_tickers:
            if get_open_orders(ticker, cfg):
                log.info(f"Order already pending for {ticker} - skipping new entry")
                continue
            try:
                trade = handle_entry(
                    item, portfolio_value=portfolio_value, cash_balance=cash_balance,
                    positions=positions, data_bundle=data_bundle, cfg=cfg,
                )
                if trade:
                    executed.append(trade)
                    positions = get_positions(cfg)
                    # An instantly filled bracket is no longer an open order; size
                    # the next entry on fresh cash (Decision 058).
                    account = get_account(cfg)
                    portfolio_value = float(account.get("portfolio_value", portfolio_value))
                    cash_balance = float(account.get("cash", cash_balance))
            except Exception as exc:  # noqa: BLE001
                log.error(f"Entry failed for {ticker}: {exc}")
        elif action == "HOLD" and ticker in held_tickers:
            try:
                executed.extend(_manage_held(item, cfg, market_open=market_open))
            except Exception as exc:  # noqa: BLE001
                log.error(f"Held-position management failed for {ticker}: {exc}")

    # --- Observability ---
    try:
        _maybe_alert_stuck_in_cash(portfolio_value, cash_balance)
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Stuck-in-cash check failed: {exc}")
    try:
        _maybe_alert_ticker_churn()
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Ticker-churn check failed: {exc}")

    _write_portfolio_snapshot(cfg)
    log.info(f"Execution complete: {len(executed)} actions taken")
    return executed


def _write_portfolio_snapshot(cfg: Config) -> None:
    """``state/portfolio.json`` for the daily summary and the API fallback —
    equity, cash and the positions as the run left them. Never fails the run."""
    try:
        account = get_account(cfg)
        positions = get_positions(cfg)
        _save("portfolio.json", {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "portfolio_value": float(account.get("portfolio_value") or 0),
            "cash": float(account.get("cash") or 0),
            "positions": [
                {k: p.get(k) for k in ("symbol", "qty", "avg_entry_price", "current_price", "market_value", "unrealized_plpc")}
                for p in positions
            ],
        })
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Portfolio snapshot failed: {exc}")


def main() -> None:
    cfg = load_config()
    if cfg.trading.trading_mode == "live":
        log.warning("=== LIVE TRADING MODE ===")
    else:
        log.info("Paper trading mode")
    for t in execute_trades(cfg):
        price_str = f"${t.get('price', 0):.2f}" if t.get("price") else "market"
        print(f"  {t['action']:4} {t.get('shares', '?'):>5} {t['ticker']:<6} @ {price_str}  [{t['trigger']}]")


if __name__ == "__main__":
    main()
