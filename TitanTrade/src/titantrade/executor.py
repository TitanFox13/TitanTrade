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
from datetime import datetime, timezone
from typing import Any

from titantrade.config import Config, STATE_DIR, load_config
from titantrade.logger import get_logger, log_decision
from titantrade.retry import fetch_with_retry
from titantrade.risk_manager import pre_trade_check

log = get_logger("executor")


# ---------------------------------------------------------------------------
# Alpaca API helpers
# ---------------------------------------------------------------------------

def _headers(cfg: Config) -> dict[str, str]:
    return {
        "APCA-API-KEY-ID": cfg.alpaca.key,
        "APCA-API-SECRET-KEY": cfg.alpaca.secret,
        "Content-Type": "application/json",
    }


def get_account(cfg: Config) -> dict[str, Any]:
    """Return account info: portfolio_value, buying_power, cash."""
    url = f"{cfg.alpaca.base_url}/v2/account"
    resp = fetch_with_retry("GET", url, headers=_headers(cfg))
    return resp.json()


def get_positions(cfg: Config) -> list[dict[str, Any]]:
    """Return all currently held positions."""
    url = f"{cfg.alpaca.base_url}/v2/positions"
    resp = fetch_with_retry("GET", url, headers=_headers(cfg))
    return resp.json()


def get_position(ticker: str, cfg: Config) -> dict[str, Any] | None:
    """Return position for ticker, or None if not held."""
    url = f"{cfg.alpaca.base_url}/v2/positions/{ticker}"
    try:
        resp = fetch_with_retry("GET", url, headers=_headers(cfg))
        return resp.json()
    except Exception:
        return None


def get_open_orders(ticker: str | None, cfg: Config) -> list[dict[str, Any]]:
    """Return open orders, optionally filtered by ticker."""
    url = f"{cfg.alpaca.base_url}/v2/orders"
    params: dict[str, str] = {"status": "open", "limit": "500"}
    if ticker:
        params["symbols"] = ticker
    resp = fetch_with_retry("GET", url, headers=_headers(cfg), params=params)
    return resp.json()


def cancel_order(order_id: str, cfg: Config) -> None:
    """Cancel a specific order by ID."""
    url = f"{cfg.alpaca.base_url}/v2/orders/{order_id}"
    fetch_with_retry("DELETE", url, headers=_headers(cfg))
    log.info(f"Cancelled order {order_id}")


def cancel_all_orders_for_ticker(ticker: str, cfg: Config) -> int:
    """Cancel all open orders for a ticker. Returns count cancelled."""
    orders = get_open_orders(ticker, cfg)
    count = 0
    for order in orders:
        try:
            cancel_order(order["id"], cfg)
            count += 1
        except Exception as exc:
            log.error(f"Failed to cancel order {order['id']} for {ticker}: {exc}")
    return count


def _is_fractional(qty: float) -> bool:
    """Return True if quantity has a fractional component."""
    return qty != int(qty)


def place_market_sell(ticker: str, qty: float, cfg: Config) -> dict[str, Any]:
    """Place an immediate market sell order."""
    url = f"{cfg.alpaca.base_url}/v2/orders"
    body = {
        "symbol": ticker,
        "qty": str(qty),
        "side": "sell",
        "type": "market",
        "time_in_force": "day",
    }
    log.info(f"Market SELL: {qty} {ticker}")
    resp = fetch_with_retry("POST", url, headers=_headers(cfg), json_body=body)
    return resp.json()


def place_limit_buy(
    ticker: str,
    qty: float,
    limit_price: float,
    cfg: Config,
    time_in_force: str = "gtc",
) -> dict[str, Any]:
    """Place a limit buy order. Default GTC so it persists across sessions."""
    url = f"{cfg.alpaca.base_url}/v2/orders"
    body = {
        "symbol": ticker,
        "qty": str(qty),
        "side": "buy",
        "type": "limit",
        "limit_price": str(round(limit_price, 2)),
        "time_in_force": time_in_force,
    }
    log.info(f"Limit BUY: {qty} {ticker} @ ${limit_price} ({time_in_force})")
    resp = fetch_with_retry("POST", url, headers=_headers(cfg), json_body=body)
    return resp.json()


def place_bracket_order(
    ticker: str,
    qty: float,
    entry_limit_price: float,
    stop_loss_price: float,
    take_profit_price: float | None,
    cfg: Config,
) -> dict[str, Any]:
    """Place a bracket order: limit entry + stop-loss + optional take-profit.

    The stop-loss and take-profit legs are native Alpaca orders that fire
    at the broker level regardless of whether our bot is running.

    Alpaca bracket orders require time_in_force = "day" (not gtc).
    The parent order and its legs are linked as OCO (one-cancels-other).
    """
    url = f"{cfg.alpaca.base_url}/v2/orders"

    order_class = "bracket" if take_profit_price else "oto"

    body: dict[str, Any] = {
        "symbol": ticker,
        "qty": str(qty),
        "side": "buy",
        "type": "limit",
        "limit_price": str(round(entry_limit_price, 2)),
        "time_in_force": "day",
        "order_class": order_class,
        "stop_loss": {
            "stop_price": str(round(stop_loss_price, 2)),
            # Stop-limit instead of pure stop, gives price improvement on volatile days
            "limit_price": str(round(stop_loss_price * 0.99, 2)),
        },
    }

    if take_profit_price:
        body["take_profit"] = {
            "limit_price": str(round(take_profit_price, 2)),
        }

    log.info(
        f"Bracket BUY: {qty} {ticker} "
        f"entry=${entry_limit_price} stop=${stop_loss_price} "
        f"tp={take_profit_price or 'none'}"
    )
    resp = fetch_with_retry("POST", url, headers=_headers(cfg), json_body=body)
    return resp.json()


def place_native_stop_loss(
    ticker: str,
    qty: float,
    stop_price: float,
    cfg: Config,
) -> dict[str, Any]:
    """Place a standalone stop-loss sell order on an existing position.

    Used when we enter via a filled limit buy and need to add the stop separately.
    Uses stop-limit with 1% buffer to avoid catastrophic slippage.
    """
    url = f"{cfg.alpaca.base_url}/v2/orders"
    body = {
        "symbol": ticker,
        "qty": str(qty),
        "side": "sell",
        "type": "stop_limit",
        "stop_price": str(round(stop_price, 2)),
        "limit_price": str(round(stop_price * 0.99, 2)),
        "time_in_force": "gtc",
    }
    log.info(f"Stop-limit SELL: {qty} {ticker} stop=${stop_price}")
    resp = fetch_with_retry("POST", url, headers=_headers(cfg), json_body=body)
    return resp.json()


def place_limit_sell(
    ticker: str,
    qty: float,
    limit_price: float,
    cfg: Config,
    time_in_force: str = "day",
) -> dict[str, Any]:
    """Place a limit sell with a small buffer below current price.

    Reduces slippage compared to market orders for non-urgent exits.
    Falls back to market sell if limit doesn't fill by close.
    """
    url = f"{cfg.alpaca.base_url}/v2/orders"
    body = {
        "symbol": ticker,
        "qty": str(qty),
        "side": "sell",
        "type": "limit",
        "limit_price": str(round(limit_price, 2)),
        "time_in_force": time_in_force,
    }
    log.info(f"Limit SELL: {qty} {ticker} @ ${limit_price:.2f}")
    resp = fetch_with_retry("POST", url, headers=_headers(cfg), json_body=body)
    return resp.json()


def close_position_at_market(ticker: str, cfg: Config) -> dict[str, Any]:
    """Close entire position at market price (Alpaca DELETE /positions/:ticker)."""
    url = f"{cfg.alpaca.base_url}/v2/positions/{ticker}"
    log.info(f"Closing position at market: {ticker}")
    resp = fetch_with_retry("DELETE", url, headers=_headers(cfg))
    return resp.json()


# ---------------------------------------------------------------------------
# Risk / sizing
# ---------------------------------------------------------------------------

def calculate_shares(
    portfolio_value: float,
    entry_price: float,
    risk_fraction: float,
) -> float:
    """Return shares to buy within the risk fraction of portfolio."""
    budget = portfolio_value * risk_fraction
    shares = round(budget / entry_price, 2)
    return max(shares, 0.0)


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def _load(filename: str) -> dict[str, Any]:
    path = STATE_DIR / filename
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def _append_trade(trade: dict[str, Any]) -> None:
    path = STATE_DIR / "trade_log.json"
    data = _load("trade_log.json")
    data.setdefault("trades", []).append(trade)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _append_near_miss(record: dict[str, Any]) -> None:
    path = STATE_DIR / "near_misses.json"
    data = _load("near_misses.json")
    data.setdefault("near_misses", []).append(record)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


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

    if not entry_price or not stop_price:
        log.warning(f"No entry/stop price for {ticker} - skipping")
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
    """
    expired = get_expired_brackets(cfg)
    if not expired:
        return []

    log.info(f"Found {len(expired)} expired bracket orders to evaluate")

    theses_by_ticker = {
        t["ticker"]: t for t in thesis_doc.get("theses", [])
    }
    held_tickers = {p["symbol"] for p in positions}

    account = get_account(cfg)
    portfolio_value = float(account.get("portfolio_value", 0))
    cash_balance = float(account.get("cash", 0))

    resubmitted: list[dict[str, Any]] = []

    for order in expired:
        ticker = order.get("symbol", "")
        thesis = theses_by_ticker.get(ticker)

        if not thesis:
            log.info(f"Skipping expired bracket for {ticker}: no active thesis")
            continue

        if thesis.get("thesis") != "BULLISH" or not thesis.get("selected_for_trading"):
            log.info(f"Skipping expired bracket for {ticker}: thesis no longer bullish/selected")
            continue

        if ticker in held_tickers:
            log.info(f"Skipping expired bracket for {ticker}: already holding position")
            continue

        # Check for existing open orders
        open_orders = get_open_orders(ticker, cfg)
        if open_orders:
            log.info(f"Skipping expired bracket for {ticker}: order already pending")
            continue

        original_entry = thesis.get("target_entry_price")
        original_stop = thesis.get("stop_loss_price")

        if not original_entry or not original_stop:
            continue

        # Dynamic entry price adjustment: use current price context
        # to adjust entry/stop/TP instead of blindly reusing Sunday's levels
        from titantrade.daily_sentry import _fetch_current_price
        current_price = _fetch_current_price(ticker, cfg)

        entry_price = original_entry
        stop_price = original_stop
        take_profit_price = thesis.get("take_profit_price")

        if current_price:
            adjusted = _adjust_entry_price(thesis, current_price)
            if adjusted is None:
                log.info(
                    f"Skipping resubmission for {ticker}: "
                    f"price ${current_price:.2f} outside adjustment range"
                )
                continue
            entry_price, stop_price, take_profit_price = adjusted
            if entry_price != original_entry:
                log.info(
                    f"Adjusted entry for {ticker}: "
                    f"${original_entry:.2f} -> ${entry_price:.2f} "
                    f"(current: ${current_price:.2f})"
                )

        stock_atr = data_bundle.get("stocks", {}).get(ticker, {}).get("atr_14")
        earnings_blocked = (
            data_bundle.get("stocks", {}).get(ticker, {})
            .get("earnings", {}).get("is_blocked", False)
        )

        check = pre_trade_check(
            ticker=ticker,
            thesis=thesis,
            portfolio_value=portfolio_value,
            cash_balance=cash_balance,
            positions=positions,
            stock_atr=stock_atr,
            earnings_blocked=earnings_blocked,
            cfg=cfg,
        )

        if not check["allowed"]:
            log.info(f"Resubmission blocked for {ticker}: {check['reason']}")
            continue

        shares = check["shares"]

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

    return resubmitted


# ---------------------------------------------------------------------------
# Trailing stop management
# ---------------------------------------------------------------------------

def _load_trailing_state() -> dict[str, Any]:
    path = STATE_DIR / "trailing_stops.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def _save_trailing_state(state: dict[str, Any]) -> None:
    with open(STATE_DIR / "trailing_stops.json", "w") as f:
        json.dump(state, f, indent=2)


def manage_trailing_stop(
    ticker: str,
    thesis: dict[str, Any],
    position: dict[str, Any],
    open_orders: list[dict[str, Any]],
    cfg: Config,
) -> None:
    """Ratchet the stop-loss upward as the position gains value.

    Uses the Alpaca position's avg_entry_price and current_price to determine
    the gain. Once gain exceeds trailing_trigger_pct, replaces the stop-loss
    with one that trails trailing_distance_pct below the high-water mark.
    """
    current_price = float(position.get("current_price", 0))
    entry_price = float(position.get("avg_entry_price", 0))
    qty = float(position.get("qty", 0))

    if not current_price or not entry_price or qty <= 0:
        return

    gain_pct = (current_price - entry_price) / entry_price
    trigger = cfg.trading.trailing_trigger_pct
    distance = cfg.trading.trailing_distance_pct

    trailing_state = _load_trailing_state()
    ts = trailing_state.get(ticker, {})

    # Update high-water mark
    hwm = max(current_price, ts.get("high_water_mark", current_price))
    ts["high_water_mark"] = hwm
    ts["entry_price"] = entry_price

    if gain_pct < trigger:
        # Not yet triggered — save state but don't trail
        ts["trailing_active"] = False
        trailing_state[ticker] = ts
        _save_trailing_state(trailing_state)
        return

    # Calculate new trailing stop
    new_stop = round(hwm * (1 - distance), 2)

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


def _cleanup_trailing_state(held_tickers: set[str]) -> None:
    """Remove trailing state for tickers that are no longer held."""
    state = _load_trailing_state()
    stale = [t for t in state if t not in held_tickers]
    for t in stale:
        del state[t]
    if stale:
        _save_trailing_state(state)


# ---------------------------------------------------------------------------
# Thesis expiry: close orphaned positions
# ---------------------------------------------------------------------------

def close_orphaned_positions(cfg: Config) -> list[dict[str, Any]]:
    """Close positions that have no active thesis or that Claude flagged for CLOSE.

    Cases:
    1. A held ticker has no entry in weekly_thesis.json (orphaned)
    2. Claude's weekly review set review_action = "CLOSE" (explicit exit)
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

        thesis = theses_by_ticker.get(ticker)

        # Case 1: Position is covered by an active thesis that isn't CLOSE
        if thesis and thesis.get("review_action") != "CLOSE":
            continue

        # Case 2: CLOSE action or no thesis at all
        if thesis and thesis.get("review_action") == "CLOSE":
            reason = f"Weekly review: CLOSE — {thesis.get('reasoning', 'Thesis invalidated')}"
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
        except Exception as exc:
            log.error(f"Failed to close orphaned position {ticker}: {exc}")

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


# ---------------------------------------------------------------------------
# Dynamic entry price adjustment for bracket resubmission
# ---------------------------------------------------------------------------

def _adjust_entry_price(
    thesis: dict[str, Any],
    current_price: float,
) -> tuple[float, float, float | None] | None:
    """Adjust entry/stop/TP prices for bracket resubmission based on current price.

    Returns (adjusted_entry, adjusted_stop, adjusted_tp) or None to skip.
    """
    original_entry = thesis.get("target_entry_price", 0)
    original_stop = thesis.get("stop_loss_price", 0)
    original_tp = thesis.get("take_profit_price")

    if not original_entry or not original_stop or not current_price:
        return None

    # Don't chase: skip if price is >5% above original entry
    if current_price > original_entry * 1.05:
        return None

    # Skip if price is below original stop (thesis invalidated)
    if current_price < original_stop:
        return None

    # If current price is at or below original entry, use the original levels
    if current_price <= original_entry:
        return original_entry, original_stop, original_tp

    # Price has moved above original entry — adjust
    # Preserve the original risk ratio
    original_risk_pct = (original_entry - original_stop) / original_entry

    # Use support level if available and close to current price
    tech_levels = thesis.get("key_technical_levels", {})
    support = tech_levels.get("support")
    resistance = tech_levels.get("resistance")

    if support and abs(current_price - support) / current_price < 0.01:
        # Price is within 1% of support — use support as entry
        adjusted_entry = round(support, 2)
    else:
        # Small discount below current price (don't market-buy, still use limit)
        adjusted_entry = round(current_price * 0.995, 2)

    # Maintain same risk ratio on the adjusted entry
    adjusted_stop = round(adjusted_entry * (1 - original_risk_pct), 2)

    # Never widen risk below the original stop
    adjusted_stop = max(adjusted_stop, original_stop)

    # Adjust take-profit proportionally, or use resistance
    adjusted_tp = None
    if original_tp and original_tp > adjusted_entry:
        if resistance and resistance > adjusted_entry:
            adjusted_tp = round(resistance, 2)
        else:
            original_rr = (original_tp - original_entry) / (original_entry - original_stop)
            adjusted_tp = round(adjusted_entry + original_rr * (adjusted_entry - adjusted_stop), 2)

    return adjusted_entry, adjusted_stop, adjusted_tp


def execute_trades(cfg: Config) -> list[dict[str, Any]]:
    """Core execution: read thesis + sentry, run risk gates, place/cancel broker orders.

    Risk gates applied to every entry:
      1. Confidence threshold (>= 0.70)
      2. Earnings blackout window (5 days)
      3. Drawdown circuit breaker (8% from peak)
      4. Cash reserve enforcement (20% minimum)
      5. Volatility-adjusted position sizing (ATR-based)
      6. Sector exposure limit (40% max per sector)
      7. Pass 2 selection filter (only trade analyst-selected stocks)
    """
    log.info("Starting trade execution")

    # --- Pre-flight safety checks (run before any thesis-based logic) ---

    # Close orphaned positions (expired thesis or missing thesis entry)
    try:
        orphan_trades = close_orphaned_positions(cfg)
        if orphan_trades:
            log.info(f"Closed {len(orphan_trades)} orphaned positions")
    except Exception as exc:
        log.error(f"Orphan position check failed: {exc}")
        orphan_trades = []

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
        elif direction == "BEARISH" and ticker in held_tickers:
            log.info(f"Thesis flipped BEARISH for {ticker} - closing position")
            try:
                cancel_all_orders_for_ticker(ticker, cfg)
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

        # ------------------------------------------------------------------
        # 4a. ADJUST review action: update stop/TP levels for held position
        # ------------------------------------------------------------------
        review_action = thesis.get("review_action", "NEW")
        if review_action == "ADJUST" and ticker in held_tickers:
            position = get_position(ticker, cfg)
            if position:
                qty = float(position.get("qty", 0))
                new_stop = thesis.get("stop_loss_price")
                new_tp = thesis.get("take_profit_price")
                if new_stop and qty > 0:
                    log.info(f"ADJUST: Replacing stop for {ticker} to ${new_stop:.2f}")
                    try:
                        cancel_all_orders_for_ticker(ticker, cfg)
                        place_native_stop_loss(ticker, qty, new_stop, cfg)
                    except Exception as exc:
                        log.error(f"Failed to adjust stop for {ticker}: {exc}")
            continue

        # ------------------------------------------------------------------
        # 4b. Holding a BULLISH position: ensure stop-loss + trailing stop
        # ------------------------------------------------------------------
        elif direction == "BULLISH" and ticker in held_tickers:
            position = get_position(ticker, cfg)
            if not position:
                continue

            open_orders = get_open_orders(ticker, cfg)
            has_stop = any(
                o.get("type") in ("stop", "stop_limit") and o.get("side") == "sell"
                for o in open_orders
            )

            qty = float(position.get("qty", 0))
            fractional = _is_fractional(qty)

            if not has_stop and not fractional:
                stop_price = thesis.get("stop_loss_price")
                if stop_price:
                    log.warning(
                        f"No stop order found for {ticker} - placing native stop now"
                    )
                    try:
                        place_native_stop_loss(ticker, qty, stop_price, cfg)
                        # Refresh orders for trailing stop check
                        open_orders = get_open_orders(ticker, cfg)
                    except Exception as exc:
                        log.error(f"Failed to place stop for {ticker}: {exc}")
            elif not has_stop and fractional:
                log.info(f"Fractional position {ticker} ({qty} shares) — no broker stop (sentry protects)")

            # Trailing stop: ratchet the stop up as the position gains (whole shares only)
            if not fractional:
                try:
                    manage_trailing_stop(ticker, thesis, position, open_orders, cfg)
                except Exception as exc:
                    log.error(f"Trailing stop management failed for {ticker}: {exc}")

    # Clean up trailing state for tickers no longer held
    try:
        final_positions = get_positions(cfg)
        _cleanup_trailing_state({p["symbol"] for p in final_positions})
    except Exception:
        pass

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
