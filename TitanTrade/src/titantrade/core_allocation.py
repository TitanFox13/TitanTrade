"""The SPY core: the residual of the book (Decision 061).

The executor passes the target it computed from the plan — exposure scale ×
investable − (held overlay + this run's planned slots) — and this module
rebalances SPY toward it with market orders when the drift exceeds the band.
Selling SPY is what funds the entries that follow in the same run; after an
exit the next run buys SPY back. There is no hedge swap: the insurance
switch lowers the target instead (cash is the hedge).
"""
from __future__ import annotations

from typing import Any

from titantrade.config import Config
from titantrade.logger import get_logger
from titantrade.broker import (
    get_account, get_positions, is_market_open, place_market_buy, place_market_sell,
)
from titantrade.market_data import get_latest_price
from titantrade.risk_manager import MIN_CASH_RESERVE_PCT
from titantrade.trade_state import _append_trade, _trade_record

log = get_logger("core_allocation")


def _is_core_ticker(ticker: str, cfg: Config) -> bool:
    """True for the core legs (SPY, the momentum ETF, the T-bill ETF when
    configured), which the plan and the gates never touch."""
    return ticker in core_tickers(cfg)


def core_tickers(cfg: Config) -> tuple[str, ...]:
    legs = [cfg.trading.core_ticker, cfg.trading.momentum_ticker]
    if cfg.trading.cash_ticker:
        legs.append(cfg.trading.cash_ticker)
    return tuple(legs)


def manage_core_position(
    cfg: Config, target_pct: float | None = None, ticker: str | None = None,
) -> dict[str, Any] | None:
    """Rebalance a core leg (default SPY; the momentum ETF when ``ticker``
    says so) toward ``target_pct`` of equity (default: the whole investable
    book). Skipped off-hours (market orders). Returns the trade record if an
    order fired, else None."""
    if not is_market_open(cfg):
        log.info("Core position management deferred — market closed")
        return None

    ticker = ticker or cfg.trading.core_ticker
    account = get_account(cfg)
    portfolio_value = float(account.get("portfolio_value", 0))
    cash_balance = float(account.get("cash", 0))
    if portfolio_value <= 0:
        return None

    core_pct = (1 - MIN_CASH_RESERVE_PCT / 100) if target_pct is None else max(0.0, min(1.0, target_pct))
    target_value = portfolio_value * core_pct
    band_value = portfolio_value * cfg.trading.core_rebalance_band_pct

    position = next((p for p in get_positions(cfg) if p.get("symbol") == ticker), None)
    current_value = float(position.get("market_value", 0)) if position else 0.0
    current_price = float(position.get("current_price", 0)) if position else 0.0
    if not current_price:
        current_price = get_latest_price(ticker, cfg) or 0.0
    if current_price <= 0:
        log.warning(f"Core: no price for {ticker}, deferring rebalance")
        return None

    drift = current_value - target_value
    if abs(drift) < band_value:
        return None

    if drift < 0:
        # Under target: buy with the cash on hand, keeping the reserve.
        spendable = min(-drift, max(cash_balance - portfolio_value * MIN_CASH_RESERVE_PCT / 100, 0.0))
        qty = float(int(spendable / current_price))
        if qty < 1:
            log.info(f"Core: under target by ${-drift:,.0f} but no spendable cash — waiting")
            return None
        place_market_buy(ticker, qty, cfg)
        action = "BUY"
    else:
        held_qty = float(position.get("qty", 0)) if position else 0.0
        qty = float(int(min(drift / current_price, held_qty)))
        if qty < 1:
            return None
        place_market_sell(ticker, qty, cfg)
        action = "SELL"

    trade = _trade_record(
        ticker=ticker, action=action, shares=qty, price=current_price,
        trigger="core_rebalance",
        reasoning=f"Core rebalance: target {core_pct:.0%} = ${target_value:,.0f}, current ${current_value:,.0f}",
        target_value=target_value, current_value=current_value,
    )
    _append_trade(trade)
    log.info(f"Core {action} {qty:.0f} {ticker} @ ${current_price:.2f} (target ${target_value:,.0f}, was ${current_value:,.0f})")
    try:
        from titantrade.notifier import notify_core_rebalance
        notify_core_rebalance(action, ticker, int(qty), current_price, target_value, current_value)
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Core rebalance notify failed: {exc}")
    return trade
