"""Observability alerts: stuck in cash, ticker churn."""

from __future__ import annotations

import datetime as dt
import json
from unittest.mock import patch

from titantrade.alerts import (
    STUCK_IN_CASH_DAYS_THRESHOLD, TICKER_CHURN_ROUND_TRIPS, _maybe_alert_stuck_in_cash,
    _maybe_alert_ticker_churn,
)


class TestStuckInCash:
    @patch("titantrade.notifier.send_discord")
    def test_alerts_once_per_day_after_threshold(self, mock_send, tmp_state_dir):
        start = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=STUCK_IN_CASH_DAYS_THRESHOLD + 1)).date().isoformat()
        (tmp_state_dir / "alert_state.json").write_text(json.dumps({"stuck_in_cash_since": start}))
        _maybe_alert_stuck_in_cash(portfolio_value=100_000, cash_balance=90_000)
        _maybe_alert_stuck_in_cash(portfolio_value=100_000, cash_balance=90_000)
        assert mock_send.call_count == 1

    @patch("titantrade.notifier.send_discord")
    def test_quiet_below_threshold(self, mock_send, tmp_state_dir):
        _maybe_alert_stuck_in_cash(portfolio_value=100_000, cash_balance=30_000)
        mock_send.assert_not_called()


class TestTickerChurn:
    @patch("titantrade.notifier.send_discord")
    def test_alerts_on_round_trips_once_per_day(self, mock_send, tmp_state_dir):
        now = dt.datetime.now(dt.timezone.utc)
        trades = []
        for i in range(TICKER_CHURN_ROUND_TRIPS):
            trades.append({"ticker": "LLY", "action": "BUY", "timestamp": (now - dt.timedelta(days=2 - i, hours=1)).isoformat(), "shares": 1, "price": 900.0, "trigger": "t", "reasoning": "t"})
            trades.append({"ticker": "LLY", "action": "SELL", "timestamp": (now - dt.timedelta(days=2 - i)).isoformat(), "shares": 1, "price": 890.0, "trigger": "t", "reasoning": "t"})
        (tmp_state_dir / "trade_log.json").write_text(json.dumps({"trades": trades}))
        _maybe_alert_ticker_churn()
        _maybe_alert_ticker_churn()
        assert mock_send.call_count == 1
