"""Discord observability alerts (stuck-in-cash, ticker churn) + alert state.

Extracted from executor.py (behavior-preserving).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from titantrade.config import STATE_DIR
from titantrade.logger import get_logger
from titantrade.trade_state import _load

log = get_logger("alerts")


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
