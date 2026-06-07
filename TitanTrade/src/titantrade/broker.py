"""Alpaca brokerage client — thin HTTP wrappers around the Alpaca REST API.

Extracted from executor.py (behavior-preserving). These are the only functions
that talk to Alpaca; everything else in the package goes through here.
"""

from __future__ import annotations

import time
from typing import Any

from titantrade.config import Config
from titantrade.logger import get_logger
from titantrade.retry import HTTPError, fetch_with_retry

log = get_logger("broker")


# Alpaca error code: "insufficient qty available for order" — typically means
# a prior cancel on the same position hasn't propagated yet (qty_available
# lags a few hundred milliseconds). Retry once after a short delay.
ALPACA_INSUFFICIENT_QTY = 40310000


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


def get_order(order_id: str, cfg: Config) -> dict[str, Any] | None:
    """Fetch a single order by ID. Returns None on 404."""
    url = f"{cfg.alpaca.base_url}/v2/orders/{order_id}"
    try:
        resp = fetch_with_retry("GET", url, headers=_headers(cfg))
        return resp.json()
    except HTTPError as exc:
        if exc.status_code == 404:
            return None
        raise


def is_market_open(cfg: Config) -> bool:
    """Return True if US equity markets are currently open.

    Off-hours cancels enter a ``pending_cancel`` state that does not resolve
    until the next market open — sometimes 12+ hours. ADJUST/orphan-close
    flows should defer until the market is open rather than trying to
    cancel-and-replace stops during off-hours.
    """
    url = f"{cfg.alpaca.base_url}/v2/clock"
    try:
        resp = fetch_with_retry("GET", url, headers=_headers(cfg))
        return bool(resp.json().get("is_open", False))
    except Exception as exc:  # noqa: BLE001
        # If we can't determine, assume open and let downstream logic deal
        # with broker errors — failing closed would block all trading on a
        # transient API blip.
        log.warning(f"Clock fetch failed, assuming market open: {exc}")
        return True


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


def place_market_buy(ticker: str, qty: float, cfg: Config) -> dict[str, Any]:
    """Place an immediate market buy order. Used by the core-allocation
    rebalancer where we want guaranteed fill, not a limit price.
    """
    url = f"{cfg.alpaca.base_url}/v2/orders"
    body = {
        "symbol": ticker,
        "qty": str(qty),
        "side": "buy",
        "type": "market",
        "time_in_force": "day",
    }
    log.info(f"Market BUY: {qty} {ticker}")
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

    Alpaca rejects fractional bracket/OTO orders ("fractional orders must be
    simple orders", HTTP 422). Whole-share callers should never hit this, but
    we floor + validate here as a hard boundary so a sizing bug upstream can
    never push a fractional qty to the broker (the production URI 0.19-share
    bug). A floored qty below 1 share is unfillable as a bracket — raise so the
    caller skips rather than silently shrinking the order.
    """
    if _is_fractional(qty):
        floored = float(int(qty))
        log.warning(
            f"Bracket qty for {ticker} was fractional ({qty}) — flooring to "
            f"{floored} (brackets require whole shares)"
        )
        qty = floored
    if qty < 1:
        raise ValueError(
            f"Bracket order for {ticker} requires >= 1 whole share, got {qty}"
        )

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


def _available_qty_from_error(exc: HTTPError) -> float | None:
    """Parse the broker-reported ``available`` qty from a 40310000 error body.

    Alpaca's insufficient-qty 403 includes the true available quantity, e.g.
    ``{"code":40310000,"available":"103", ...}``. When our intended qty is
    stale (the classic TP1 / gap-down race), this is the number of shares we
    can actually place a stop on right now. Returns the float or None if the
    body doesn't carry a usable value.
    """
    data = exc.data if isinstance(exc.data, dict) else None
    if not data:
        return None
    raw = data.get("available")
    if raw is None:
        return None
    try:
        return float(raw)
    except (ValueError, TypeError):
        return None


# How long to wait for a cancel to reach the ``canceled`` state before giving
# up on the qty-race retry. During market hours this happens in 1-5 s; during
# off-hours the order can sit in ``pending_cancel`` until the next market open
# (which is why the ADJUST flow now skips altogether when ``is_market_open``
# is False).
CANCEL_SETTLE_TIMEOUT_SECONDS = 120.0


CANCEL_SETTLE_POLL_INTERVAL = 1.0


# Terminal order states — once an order reaches one of these, Alpaca has
# released any qty it was holding.
_TERMINAL_ORDER_STATES = {"canceled", "cancelled", "filled", "rejected", "expired", "done_for_day"}


def _wait_for_order_canceled(
    order_id: str,
    cfg: Config,
    timeout_seconds: float = CANCEL_SETTLE_TIMEOUT_SECONDS,
) -> str | None:
    """Poll an order's status until it reaches a terminal state.

    Returns the final status string (e.g. ``"canceled"``) on success, or
    ``None`` on timeout. Polling the order's own status is the deterministic
    way to know when its held qty has been released — polling
    ``position.qty_available`` was lossy because Alpaca's position-side
    accounting can lag the order-side state by several seconds.
    """
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            order = get_order(order_id, cfg)
            if order is None:
                # 404 — order has been GC'd, definitely no longer holding qty
                return "canceled"
            status = str(order.get("status", "")).lower()
            if status in _TERMINAL_ORDER_STATES:
                return status
        except Exception as exc:  # noqa: BLE001
            log.debug(f"Order fetch during cancel-wait failed for {order_id}: {exc}")
        time.sleep(CANCEL_SETTLE_POLL_INTERVAL)
    return None


def place_native_stop_loss(
    ticker: str,
    qty: float,
    stop_price: float,
    cfg: Config,
) -> dict[str, Any]:
    """Place a standalone stop-loss sell order on an existing position.

    Uses a stop-limit with a 1% buffer below the stop for slippage protection.

    Error handling:
      - On Alpaca 40310000 ("insufficient qty available"), we POLL the
        blocking order named in ``related_orders`` until it reaches a terminal
        state (up to 120 s), then retry the same stop-limit. This replaces an
        older 2-second blind sleep that sometimes wasn't long enough in
        production — leaving held positions without a stop for a ~6-hour
        window until the next executor run.
      - If the retry STILL reports insufficient qty (or Alpaca never named a
        blocking order to poll), we clamp to the broker-reported ``available``
        quantity and place a stop on whatever shares actually exist. A stop on
        100 of 103 intended shares beats no stop at all — this is the
        last-resort guarantee that a position is never left bare (the FCX
        TP1/gap-down race that stranded positions with no stop in production).
      - On any other 4xx we fall back to a plain stop order — historically
        Alpaca paper accounts have rejected stop-limit for some asset types.
    """
    url = f"{cfg.alpaca.base_url}/v2/orders"

    def _post_stop_limit(stop_qty: float) -> dict[str, Any]:
        body = {
            "symbol": ticker,
            "qty": str(stop_qty),
            "side": "sell",
            "type": "stop_limit",
            "stop_price": str(round(stop_price, 2)),
            "limit_price": str(round(stop_price * 0.99, 2)),
            "time_in_force": "gtc",
        }
        log.info(f"Stop-limit SELL: {stop_qty} {ticker} stop=${stop_price}")
        return fetch_with_retry(
            "POST", url, headers=_headers(cfg), json_body=body
        ).json()

    def _clamp_and_retry(exc: HTTPError) -> dict[str, Any]:
        """Last resort: re-place the stop on the broker-reported available qty
        so the position is never stranded without a stop."""
        available = _available_qty_from_error(exc)
        # Whole-share stops for clarity; available may come back as e.g. "103".
        clamped = float(int(available)) if available and available >= 1 else 0.0
        if clamped <= 0 or clamped >= qty:
            # Nothing safe to clamp to (available is 0, unparseable, or not
            # actually smaller than what we asked for) — propagate.
            raise exc
        log.warning(
            f"Stop for {ticker}: clamping requested {qty} → broker-available "
            f"{clamped} shares and retrying so the position is not left bare"
        )
        resp = _post_stop_limit(clamped)
        log.warning(
            f"Stop for {ticker} placed on {clamped} available shares "
            f"(requested {qty}) — remainder is held by an in-flight order"
        )
        return resp

    try:
        return _post_stop_limit(qty)
    except HTTPError as exc:
        if exc.error_code == ALPACA_INSUFFICIENT_QTY:
            # Qty race — a recent cancel hasn't reached the ``canceled`` state
            # yet. Alpaca's 403 helpfully tells us WHICH order is holding the
            # qty, so we poll that specific order until it terminates.
            related = exc.data.get("related_orders") if isinstance(exc.data, dict) else None
            blocking_id = related[0] if isinstance(related, list) and related else None
            if not blocking_id:
                # Can't poll — but Alpaca told us how many shares ARE available.
                # Clamp to that rather than leaving the position unprotected.
                log.warning(
                    f"Qty race for {ticker} but Alpaca did not name a blocking "
                    f"order — clamping to available qty. Body: {exc.body[:200]}"
                )
                return _clamp_and_retry(exc)

            log.warning(
                f"Qty race for {ticker} (code 40310000) — blocked by order "
                f"{blocking_id}, polling its status (up to "
                f"{CANCEL_SETTLE_TIMEOUT_SECONDS:.0f}s)"
            )
            t0 = time.time()
            final_status = _wait_for_order_canceled(blocking_id, cfg)
            waited = time.time() - t0
            if final_status is None:
                log.error(
                    f"Blocking order {blocking_id} for {ticker} never reached "
                    f"a terminal state within {CANCEL_SETTLE_TIMEOUT_SECONDS:.0f}s "
                    f"— giving up. (Common during off-hours; the ADJUST flow "
                    f"should be gated on ``is_market_open``.)"
                )
                raise

            log.info(
                f"Blocking order {blocking_id} for {ticker} reached "
                f"'{final_status}' after {waited:.1f}s — retrying stop-limit"
            )
            try:
                resp = _post_stop_limit(qty)
                log.info(
                    f"Stop-limit for {ticker} succeeded after cancel settled "
                    f"({waited:.1f}s)"
                )
                return resp
            except HTTPError as exc2:
                if exc2.error_code == ALPACA_INSUFFICIENT_QTY:
                    # Cancel settled but qty is still short (the sell that
                    # reduced the position is itself still settling). Clamp to
                    # whatever is available now — never return bare.
                    log.error(
                        f"Stop-limit for {ticker} still short after cancel "
                        f"settled: {exc2.error_message} — clamping to available"
                    )
                    return _clamp_and_retry(exc2)
                log.error(
                    f"Stop-limit for {ticker} failed after cancel settled: "
                    f"code={exc2.error_code} msg={exc2.error_message}"
                )
                raise

        # Any other 4xx: fall through to the plain-stop fallback below.
        log.warning(
            f"Stop-limit rejected for {ticker} "
            f"(code={exc.error_code}, msg={exc.error_message}) — falling back to plain stop"
        )

    # Fallback: plain stop order (market sell when stop triggers).
    plain_stop_body = {
        "symbol": ticker,
        "qty": str(qty),
        "side": "sell",
        "type": "stop",
        "stop_price": str(round(stop_price, 2)),
        "time_in_force": "gtc",
    }
    log.info(f"Stop SELL (fallback): {qty} {ticker} stop=${stop_price}")
    resp = fetch_with_retry(
        "POST", url, headers=_headers(cfg), json_body=plain_stop_body
    )
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
