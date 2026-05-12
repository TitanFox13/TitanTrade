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

# Alpaca error code: "insufficient qty available for order" — typically means
# a prior cancel on the same position hasn't propagated yet (qty_available
# lags a few hundred milliseconds). Retry once after a short delay.
ALPACA_INSUFFICIENT_QTY = 40310000

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
      - On Alpaca 40310000 ("insufficient qty available"), we POLL
        ``qty_available`` until it meets ``qty`` (up to 30 s), then retry
        the same stop-limit. This replaces an older 2-second blind sleep
        that sometimes wasn't long enough in production — leaving held
        positions without a stop for a ~6-hour window until the next
        executor run.
      - On any other 4xx we fall back to a plain stop order — historically
        Alpaca paper accounts have rejected stop-limit for some asset types.
    """
    url = f"{cfg.alpaca.base_url}/v2/orders"
    stop_limit_body = {
        "symbol": ticker,
        "qty": str(qty),
        "side": "sell",
        "type": "stop_limit",
        "stop_price": str(round(stop_price, 2)),
        "limit_price": str(round(stop_price * 0.99, 2)),
        "time_in_force": "gtc",
    }
    log.info(f"Stop-limit SELL: {qty} {ticker} stop=${stop_price}")

    try:
        resp = fetch_with_retry(
            "POST", url, headers=_headers(cfg), json_body=stop_limit_body
        )
        return resp.json()
    except HTTPError as exc:
        if exc.error_code == ALPACA_INSUFFICIENT_QTY:
            # Qty race — a recent cancel hasn't reached the ``canceled`` state
            # yet. Alpaca's 403 helpfully tells us WHICH order is holding the
            # qty, so we poll that specific order until it terminates.
            related = exc.data.get("related_orders") if isinstance(exc.data, dict) else None
            blocking_id = related[0] if isinstance(related, list) and related else None
            if not blocking_id:
                log.error(
                    f"Qty race for {ticker} but Alpaca did not name a blocking "
                    f"order — cannot poll. Body: {exc.body[:200]}"
                )
                raise

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
                resp = fetch_with_retry(
                    "POST", url, headers=_headers(cfg), json_body=stop_limit_body
                )
                log.info(
                    f"Stop-limit for {ticker} succeeded after cancel settled "
                    f"({waited:.1f}s)"
                )
                return resp.json()
            except HTTPError as exc2:
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
# Re-entry cooldown (prevents whipsaw after ABORT)
# ---------------------------------------------------------------------------

# After we ABORT a ticker (sentry, price-check, or thesis-flip exit) we lock
# new entries on that ticker for this many hours. Without this, the executor
# would re-buy on the next run because Claude's weekly thesis is still
# BULLISH — producing the documented "sell low, buy higher" cycles (LLY and
# FCX each round-tripped 3+ times in a single week in prod logs).
REENTRY_COOLDOWN_HOURS = 72

# Maximum expired-bracket attempts we'll keep resubmitting before giving up.
# Production showed CRWD running this loop daily for 10+ days, chasing the
# price up without ever filling. Cap is reset at the next weekly thesis.
MAX_BRACKET_ATTEMPTS = 5


def _load_abort_cooldowns() -> dict[str, dict[str, Any]]:
    """Return {ticker: {aborted_at, reason}} from disk."""
    path = STATE_DIR / "abort_cooldown.json"
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_abort_cooldowns(data: dict[str, dict[str, Any]]) -> None:
    with open(STATE_DIR / "abort_cooldown.json", "w") as f:
        json.dump(data, f, indent=2)


def _record_abort_cooldown(ticker: str, reason: str) -> None:
    """Record an ABORT so re-entries are suppressed for REENTRY_COOLDOWN_HOURS."""
    data = _load_abort_cooldowns()
    data[ticker] = {
        "aborted_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason[:200],  # cap to keep file small
    }
    _save_abort_cooldowns(data)


def _is_in_cooldown(ticker: str) -> tuple[bool, float]:
    """Return ``(in_cooldown, hours_since_abort)``.

    Also prunes expired entries (older than the cooldown window) so the file
    doesn't grow unbounded.
    """
    data = _load_abort_cooldowns()
    entry = data.get(ticker)
    if not entry:
        return False, 0.0
    try:
        aborted_at = datetime.fromisoformat(entry["aborted_at"])
    except (ValueError, KeyError, TypeError):
        # Bad data — clean up and don't apply
        data.pop(ticker, None)
        _save_abort_cooldowns(data)
        return False, 0.0
    hours = (datetime.now(timezone.utc) - aborted_at).total_seconds() / 3600
    if hours >= REENTRY_COOLDOWN_HOURS:
        # Expired — clean up
        data.pop(ticker, None)
        _save_abort_cooldowns(data)
        return False, hours
    return True, hours


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

    if not entry_price or not stop_price:
        log.warning(f"No entry/stop price for {ticker} - skipping")
        return None

    # Re-entry cooldown: don't buy back into a ticker we just ABORTed.
    in_cooldown, hours_since = _is_in_cooldown(ticker)
    if in_cooldown:
        remaining = REENTRY_COOLDOWN_HOURS - hours_since
        log.info(
            f"Skipping {ticker} bullish entry: in re-entry cooldown "
            f"({hours_since:.1f}h since ABORT, {remaining:.1f}h remaining)"
        )
        return None

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

        # Price-chase guard: if we've already failed to fill N times, the
        # price has clearly run away. Stop resubmitting until next weekly
        # thesis refresh, when Claude will reassess.
        attempts = attempts_per_ticker.get(ticker, 0)
        if attempts > MAX_BRACKET_ATTEMPTS:
            log.info(
                f"Skipping expired bracket for {ticker}: {attempts} prior "
                f"expirations (cap {MAX_BRACKET_ATTEMPTS}) — price chase, "
                f"waiting for next weekly thesis"
            )
            continue

        # Re-entry cooldown: if we ABORTed this ticker recently, don't resubmit
        in_cooldown, hours_since = _is_in_cooldown(ticker)
        if in_cooldown:
            log.info(
                f"Skipping expired bracket for {ticker}: in re-entry cooldown "
                f"({hours_since:.1f}h since ABORT, "
                f"{REENTRY_COOLDOWN_HOURS - hours_since:.1f}h remaining)"
            )
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
                    # hours when the market is closed. The OLD stop is still
                    # active on the book protecting the position, so deferring
                    # the price update until the next market-hours run is safe.
                    if not market_open and existing_stop is not None:
                        log.info(
                            f"ADJUST {ticker}: market closed — deferring stop "
                            f"update from ${existing_price:.2f} to "
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

            # Trailing stop: ratchet the stop up as the position gains
            # (whole shares only). Skipped off-hours for the same reason as
            # ADJUST — the cancel would sit in pending_cancel until next open
            # and leave the position with no stop. The existing stop is on
            # the book and still protective; trailing can wait one cycle.
            if not fractional and market_open:
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
