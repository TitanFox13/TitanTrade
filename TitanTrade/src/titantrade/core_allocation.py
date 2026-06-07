"""Always-on core market allocation (SPY) + stress hedge swap.

Extracted from executor.py (behavior-preserving).
"""

from __future__ import annotations

from typing import Any

from titantrade.config import Config
from titantrade.logger import get_logger
from titantrade.broker import (
    get_account, get_positions, place_market_buy, place_market_sell,
    cancel_all_orders_for_ticker, close_position_at_market, is_market_open,
)
from titantrade.trade_state import _append_trade, _load, _trade_record

log = get_logger("core_allocation")


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
