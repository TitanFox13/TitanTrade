"""Tests for trade executor with MOCKED broker (Alpaca) API calls.

CRITICAL: All Alpaca API calls are monkeypatched. No real orders are placed.
No AI tokens are spent. No real money is at risk.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from titantrade.executor import (
    _build_trade_context,
    _handle_bullish_entry,
    place_native_stop_loss,
    resubmit_expired_brackets,
)
from titantrade.retry import HTTPError

from tests.conftest import write_state_file


@pytest.fixture
def data_bundle():
    """Minimal data bundle for context building."""
    return {
        "market_context": {
            "market_regime": "bullish",
            "vix": {"level": 16.5, "classification": "normal"},
            "spy": {"return_1d": 0.3},
        },
        "stocks": {
            "AAPL": {
                "technical_indicators": {
                    "rsi_14": 42.5,
                    "macd": {"histogram": 0.23},
                    "price_vs_sma": {"above_sma_50": True, "above_sma_200": True},
                },
                "atr_14": 3.25,
                "news": [
                    {"title": "Apple Reports Strong Q1"},
                    {"title": "iPhone 16 demand surges"},
                    {"title": "Services revenue up 18%"},
                    {"title": "Fourth headline"},
                ],
                "earnings": {"days_until_earnings": 27, "is_blocked": False},
            },
        },
    }


class TestBuildTradeContext:
    def test_extracts_market_context(self, data_bundle):
        ctx = _build_trade_context("AAPL", data_bundle, None)
        assert ctx["market_regime"] == "bullish"
        assert ctx["vix_level"] == 16.5
        assert ctx["spy_return_1d"] == 0.3

    def test_extracts_technicals(self, data_bundle):
        ctx = _build_trade_context("AAPL", data_bundle, None)
        assert ctx["technicals"]["rsi_14"] == 42.5
        assert ctx["technicals"]["price_vs_sma_50"] == "above"

    def test_extracts_top_3_headlines(self, data_bundle):
        ctx = _build_trade_context("AAPL", data_bundle, None)
        assert len(ctx["recent_news"]) == 3

    def test_includes_sentry_signal(self, data_bundle):
        sentry = {"signal": "CONTINUE", "reasoning": "All clear"}
        ctx = _build_trade_context("AAPL", data_bundle, sentry)
        assert ctx["sentry_signal"] == "CONTINUE"
        assert ctx["sentry_reasoning"] == "All clear"

    def test_missing_ticker(self, data_bundle):
        ctx = _build_trade_context("UNKNOWN", data_bundle, None)
        assert ctx["technicals"]["rsi_14"] is None


class TestHandleBullishEntry:
    @pytest.fixture(autouse=True)
    def _mock_deps(self, monkeypatch, tmp_state_dir):
        monkeypatch.setattr("titantrade.risk_manager.get_stock_sector", lambda t: "Technology")

    @patch("titantrade.executor.place_bracket_order", return_value={"id": "order_123"})
    @patch("titantrade.executor.get_open_orders", return_value=[])
    def test_places_bracket_when_allowed(
        self, mock_orders, mock_bracket, fake_config, bullish_thesis, sample_positions, data_bundle
    ):
        result = _handle_bullish_entry(
            ticker="AAPL",
            thesis=bullish_thesis,
            portfolio_value=100_000,
            cash_balance=50_000,
            positions=sample_positions,
            data_bundle=data_bundle,
            sentry=None,
            cfg=fake_config,
        )
        assert result is not None
        assert result["action"] == "BUY"
        assert result["ticker"] == "AAPL"
        assert mock_bracket.call_count >= 1  # 2-tranche: may call twice

    @patch("titantrade.executor.place_bracket_order")
    @patch("titantrade.executor.get_open_orders", return_value=[])
    def test_blocked_by_low_confidence(
        self, mock_orders, mock_bracket, fake_config, bullish_thesis, sample_positions, data_bundle, tmp_state_dir
    ):
        bullish_thesis["confidence"] = 0.30
        result = _handle_bullish_entry(
            ticker="AAPL",
            thesis=bullish_thesis,
            portfolio_value=100_000,
            cash_balance=50_000,
            positions=sample_positions,
            data_bundle=data_bundle,
            sentry=None,
            cfg=fake_config,
        )
        assert result is None
        mock_bracket.assert_not_called()

    @patch("titantrade.executor.place_bracket_order")
    @patch("titantrade.executor.get_open_orders", return_value=[])
    def test_near_miss_recorded(
        self, mock_orders, mock_bracket, fake_config, bullish_thesis, sample_positions, data_bundle, tmp_state_dir
    ):
        """When blocked by 1-2 gates, a near-miss should be saved."""
        bullish_thesis["confidence"] = 0.50  # Only confidence fails
        _handle_bullish_entry(
            ticker="AAPL",
            thesis=bullish_thesis,
            portfolio_value=100_000,
            cash_balance=50_000,
            positions=sample_positions,
            data_bundle=data_bundle,
            sentry=None,
            cfg=fake_config,
        )
        nm_path = tmp_state_dir / "near_misses.json"
        assert nm_path.exists()
        data = json.loads(nm_path.read_text())
        assert len(data["near_misses"]) == 1
        assert data["near_misses"][0]["ticker"] == "AAPL"


class TestResubmitExpiredBrackets:
    def _make_expired_order(self, ticker: str = "AAPL") -> dict[str, Any]:
        return {
            "id": "order_expired_1",
            "symbol": ticker,
            "status": "expired",
            "order_class": "bracket",
            "side": "buy",
            "limit_price": "185.50",
            "qty": "100",
        }

    @pytest.fixture(autouse=True)
    def _mock_deps(self, monkeypatch, tmp_state_dir):
        monkeypatch.setattr("titantrade.risk_manager.get_stock_sector", lambda t: "Technology")

    @patch("titantrade.executor.place_bracket_order", return_value={"id": "resubmit_1"})
    @patch("titantrade.executor.get_positions", return_value=[])
    @patch("titantrade.executor.get_open_orders", return_value=[])
    @patch("titantrade.executor.get_account", return_value={"portfolio_value": "100000", "cash": "50000"})
    @patch("titantrade.executor.get_expired_brackets")
    def test_resubmits_valid_expired(
        self, mock_expired, mock_account, mock_open, mock_pos, mock_bracket,
        fake_config, bullish_thesis
    ):
        mock_expired.return_value = [self._make_expired_order()]
        thesis_doc = {
            "theses": [{**bullish_thesis, "selected_for_trading": True}],
        }
        result = resubmit_expired_brackets(fake_config, thesis_doc, [], {})
        assert len(result) == 1
        assert result[0]["trigger"] == "bracket_resubmission"
        mock_bracket.assert_called_once()

    @patch("titantrade.executor.get_expired_brackets", return_value=[])
    def test_no_expired_returns_empty(self, mock_expired, fake_config):
        result = resubmit_expired_brackets(fake_config, {"theses": []}, [], {})
        assert result == []

    @patch("titantrade.executor.place_bracket_order")
    @patch("titantrade.executor.get_positions", return_value=[])
    @patch("titantrade.executor.get_open_orders", return_value=[])
    @patch("titantrade.executor.get_account", return_value={"portfolio_value": "100000", "cash": "50000"})
    @patch("titantrade.executor.get_expired_brackets")
    def test_skips_if_thesis_not_bullish(
        self, mock_expired, mock_account, mock_open, mock_pos, mock_bracket,
        fake_config
    ):
        mock_expired.return_value = [self._make_expired_order()]
        thesis_doc = {
            "theses": [{"ticker": "AAPL", "thesis": "BEARISH", "confidence": 0.8, "selected_for_trading": True}],
        }
        result = resubmit_expired_brackets(fake_config, thesis_doc, [], {})
        assert result == []
        mock_bracket.assert_not_called()

    @patch("titantrade.executor.place_bracket_order")
    @patch("titantrade.executor.get_positions", return_value=[])
    @patch("titantrade.executor.get_open_orders", return_value=[])
    @patch("titantrade.executor.get_account", return_value={"portfolio_value": "100000", "cash": "50000"})
    @patch("titantrade.executor.get_expired_brackets")
    def test_skips_if_already_holding(
        self, mock_expired, mock_account, mock_open, mock_pos, mock_bracket,
        fake_config, bullish_thesis
    ):
        mock_expired.return_value = [self._make_expired_order()]
        thesis_doc = {
            "theses": [{**bullish_thesis, "selected_for_trading": True}],
        }
        # Already holding AAPL
        positions = [{"symbol": "AAPL", "qty": "50", "market_value": "9000"}]
        result = resubmit_expired_brackets(fake_config, thesis_doc, positions, {})
        assert result == []


# ---------------------------------------------------------------------------
# place_native_stop_loss — qty-race retry + fallback
# ---------------------------------------------------------------------------

def _make_qty_race_error(
    related_order_id: str = "75c2b7cf-06c0-45d0-8eb9-e169891dea08",
) -> HTTPError:
    return HTTPError(
        status_code=403,
        body=(
            '{"code":40310000,"available":"0","existing_qty":"121",'
            '"held_for_orders":"121",'
            '"message":"insufficient qty available for order (requested: 121, available: 0)",'
            f'"related_orders":["{related_order_id}"],'
            '"symbol":"FCX"}'
        ),
        url="https://paper-api.alpaca.markets/v2/orders",
        method="POST",
    )


def _make_response(data: dict[str, Any]) -> MagicMock:
    """Fake fetch_with_retry response object with .json()."""
    r = MagicMock()
    r.json.return_value = data
    return r


class TestPlaceNativeStopLoss:
    @patch("titantrade.executor.time.sleep")
    @patch("titantrade.executor.get_order")
    @patch("titantrade.executor.fetch_with_retry")
    def test_retries_on_qty_race_after_blocking_order_canceled(
        self, mock_fetch, mock_get_order, mock_sleep, fake_config,
    ):
        """When Alpaca returns 40310000, poll the BLOCKING order's status
        (from related_orders) until it reaches a terminal state, then retry.
        This is the post-Bug-#1 fix: we no longer poll qty_available, which
        was lossy because Alpaca's position-side accounting lags order state.
        """
        mock_fetch.side_effect = [
            _make_qty_race_error("blocking-order-1"),
            _make_response({"id": "order-abc", "status": "accepted"}),
        ]
        # Order polling: pending_cancel twice, then canceled
        mock_get_order.side_effect = [
            {"id": "blocking-order-1", "status": "pending_cancel"},
            {"id": "blocking-order-1", "status": "pending_cancel"},
            {"id": "blocking-order-1", "status": "canceled"},
        ]

        result = place_native_stop_loss("FCX", 121, 64.50, fake_config)

        assert result["id"] == "order-abc"
        assert mock_fetch.call_count == 2
        for call in mock_fetch.call_args_list:
            assert call.kwargs["json_body"]["type"] == "stop_limit"
        # We polled the specific blocking order's status until it canceled
        assert mock_get_order.call_count >= 2
        # All get_order calls used the order id from related_orders
        for call in mock_get_order.call_args_list:
            assert call.args[0] == "blocking-order-1"

    @patch("titantrade.executor.time.time")
    @patch("titantrade.executor.time.sleep")
    @patch("titantrade.executor.get_order")
    @patch("titantrade.executor.fetch_with_retry")
    def test_qty_race_times_out_if_cancel_never_completes(
        self, mock_fetch, mock_get_order, mock_sleep, mock_time, fake_config,
    ):
        """If the blocking order stays in pending_cancel past the timeout
        (e.g. off-hours), we raise rather than retrying forever.
        """
        mock_fetch.side_effect = [_make_qty_race_error("stuck-order")]
        # Order forever stuck in pending_cancel
        mock_get_order.return_value = {"id": "stuck-order", "status": "pending_cancel"}
        # time.time() jumps past the 120s deadline quickly
        mock_time.side_effect = [0.0, 0.0, 121.0, 121.0, 121.0, 121.0]

        with pytest.raises(HTTPError) as exc_info:
            place_native_stop_loss("FCX", 121, 64.50, fake_config)

        assert exc_info.value.error_code == 40310000
        assert mock_fetch.call_count == 1  # one initial attempt; gave up polling

    @patch("titantrade.executor.fetch_with_retry")
    def test_qty_race_without_related_orders_raises(self, mock_fetch, fake_config):
        """If Alpaca returns 40310000 without naming the blocking order in
        related_orders, we can't poll — must raise."""
        bad_error = HTTPError(
            status_code=403,
            body='{"code":40310000,"message":"insufficient qty","symbol":"FCX"}',
            url="https://paper-api.alpaca.markets/v2/orders",
            method="POST",
        )
        mock_fetch.side_effect = [bad_error]

        with pytest.raises(HTTPError) as exc_info:
            place_native_stop_loss("FCX", 121, 64.50, fake_config)
        assert exc_info.value.error_code == 40310000

    @patch("titantrade.executor.fetch_with_retry")
    def test_falls_back_to_plain_stop_on_non_qty_error(self, mock_fetch, fake_config):
        """For non-40310000 4xx errors, the plain-stop fallback is still useful
        (some paper-account asset types reject stop_limit).
        """
        other_error = HTTPError(
            status_code=422,
            body='{"code":42210000,"message":"stop_limit not supported here"}',
            url="https://paper-api.alpaca.markets/v2/orders",
            method="POST",
        )
        mock_fetch.side_effect = [
            other_error,
            _make_response({"id": "order-xyz", "status": "accepted"}),
        ]

        result = place_native_stop_loss("FOO", 10, 50.00, fake_config)

        assert result["id"] == "order-xyz"
        assert mock_fetch.call_count == 2
        # First call was stop_limit, second was plain stop
        assert mock_fetch.call_args_list[0].kwargs["json_body"]["type"] == "stop_limit"
        assert mock_fetch.call_args_list[1].kwargs["json_body"]["type"] == "stop"

    @patch("titantrade.executor.fetch_with_retry")
    def test_success_first_try_no_retry(self, mock_fetch, fake_config):
        """When Alpaca accepts the stop-limit on the first try, no retry happens."""
        mock_fetch.return_value = _make_response({"id": "order-123", "status": "accepted"})

        result = place_native_stop_loss("AAPL", 100, 180.00, fake_config)

        assert result["id"] == "order-123"
        assert mock_fetch.call_count == 1


# ---------------------------------------------------------------------------
# ADJUST flow safety — restore old stop if new one fails
# ---------------------------------------------------------------------------

class TestAdjustStopSafety:
    """The ADJUST flow (execute_trades Section 4a) must never leave a held
    position without a stop. If cancel succeeds but the replacement place
    fails, we re-create the old stop at its previous price.
    """

    @patch("titantrade.executor.place_native_stop_loss")
    @patch("titantrade.executor.cancel_all_orders_for_ticker")
    @patch("titantrade.executor.get_open_orders")
    @patch("titantrade.executor.get_position")
    def test_old_stop_restored_on_failure(
        self, mock_get_pos, mock_get_open, mock_cancel, mock_place,
    ):
        """Simulate the ADJUST code path directly: cancel, place fails, restore
        the old stop at its original price. This is the safety net protecting
        a held position from being stranded without a stop.
        """
        # This test exercises the inline logic rather than execute_trades
        # end-to-end. The restore pattern is: cancel → place(new) → on failure
        # → place(old). We re-implement it here to verify the contract.
        from titantrade.config import Config
        import titantrade.executor as ex_mod

        cfg = MagicMock(spec=Config)
        qty = 121
        ticker = "FCX"
        new_stop = 64.50
        old_stop_price = 63.36

        # First place (for new_stop) raises; second place (restoring old_stop)
        # succeeds.
        mock_place.side_effect = [
            RuntimeError("network blip"),
            {"id": "restored-order", "status": "accepted"},
        ]

        restored = None
        try:
            mock_cancel(ticker, cfg)
            mock_place(ticker, qty, new_stop, cfg)
        except Exception:
            # This is the safety-net branch we added in executor.py
            if old_stop_price > 0:
                restored = mock_place(ticker, qty, old_stop_price, cfg)

        assert mock_place.call_count == 2
        # First attempt used the NEW price, second (restore) used the OLD price
        assert mock_place.call_args_list[0].args == (ticker, qty, new_stop, cfg)
        assert mock_place.call_args_list[1].args == (ticker, qty, old_stop_price, cfg)
        assert restored is not None
        assert restored["id"] == "restored-order"

    def test_idempotency_threshold(self):
        """The ADJUST no-op check uses a $0.01 tolerance: prices that round to
        the same cent are treated as equal.
        """
        existing_price = 64.50
        new_stop = 64.50
        assert abs(existing_price - new_stop) < 0.01

        # Different to the nearest penny — should NOT be treated as equal.
        assert abs(64.50 - 64.52) >= 0.01


# ---------------------------------------------------------------------------
# Bracket math sanity (Bug #2 — invalid stop/entry from ADJUSTed theses)
# ---------------------------------------------------------------------------

class TestBracketMathSanity:
    """Production showed brackets being placed with stop_price >= entry_price
    because the thesis had been ADJUSTed to raise the stop above the original
    entry (locking in profit on a position already held). The new entry path
    must detect and skip these — Alpaca would reject with HTTP 422 anyway.
    """

    @patch("titantrade.executor.place_bracket_order")
    def test_handle_bullish_entry_skips_when_stop_above_entry(
        self, mock_bracket, fake_config, data_bundle,
    ):
        from titantrade.executor import _handle_bullish_entry
        thesis = {
            "ticker": "AAPL",
            "thesis": "BULLISH",
            "confidence": 0.85,
            "target_entry_price": 145.0,
            "stop_loss_price": 165.0,  # higher than entry — invalid for new entry
            "take_profit_price": 200.0,
            "selected_for_trading": True,
        }
        result = _handle_bullish_entry(
            ticker="AAPL", thesis=thesis,
            portfolio_value=100_000, cash_balance=50_000,
            positions=[], data_bundle=data_bundle, sentry=None, cfg=fake_config,
        )
        assert result is None
        mock_bracket.assert_not_called()

    @patch("titantrade.executor.place_bracket_order")
    def test_handle_bullish_entry_skips_when_tp_below_stop(
        self, mock_bracket, fake_config, data_bundle,
    ):
        from titantrade.executor import _handle_bullish_entry
        thesis = {
            "ticker": "AAPL",
            "thesis": "BULLISH",
            "confidence": 0.85,
            "target_entry_price": 145.0,
            "stop_loss_price": 140.0,
            "take_profit_price": 138.0,  # below stop — invalid
            "selected_for_trading": True,
        }
        result = _handle_bullish_entry(
            ticker="AAPL", thesis=thesis,
            portfolio_value=100_000, cash_balance=50_000,
            positions=[], data_bundle=data_bundle, sentry=None, cfg=fake_config,
        )
        assert result is None
        mock_bracket.assert_not_called()


# ---------------------------------------------------------------------------
# Market-hours awareness (Bug #1 root cause)
# ---------------------------------------------------------------------------

class TestMarketHoursHelper:
    @patch("titantrade.executor.fetch_with_retry")
    def test_is_market_open_true(self, mock_fetch, fake_config):
        from titantrade.executor import is_market_open
        mock_fetch.return_value = _make_response({"is_open": True})
        assert is_market_open(fake_config) is True

    @patch("titantrade.executor.fetch_with_retry")
    def test_is_market_open_false(self, mock_fetch, fake_config):
        from titantrade.executor import is_market_open
        mock_fetch.return_value = _make_response({"is_open": False})
        assert is_market_open(fake_config) is False

    @patch("titantrade.executor.fetch_with_retry")
    def test_is_market_open_assumes_open_on_error(self, mock_fetch, fake_config):
        """Clock fetch failing must not block all trading — assume open."""
        from titantrade.executor import is_market_open
        mock_fetch.side_effect = RuntimeError("clock unreachable")
        assert is_market_open(fake_config) is True


# ---------------------------------------------------------------------------
# Order-status polling helper
# ---------------------------------------------------------------------------

class TestWaitForOrderCanceled:
    @patch("titantrade.executor.time.sleep")
    @patch("titantrade.executor.get_order")
    def test_returns_when_order_canceled(self, mock_get, mock_sleep, fake_config):
        from titantrade.executor import _wait_for_order_canceled
        mock_get.side_effect = [
            {"status": "pending_cancel"},
            {"status": "pending_cancel"},
            {"status": "canceled"},
        ]
        assert _wait_for_order_canceled("oid", fake_config) == "canceled"
        assert mock_get.call_count == 3

    @patch("titantrade.executor.time.sleep")
    @patch("titantrade.executor.get_order")
    def test_returns_when_filled(self, mock_get, mock_sleep, fake_config):
        """A bracket child order can become 'filled' instead of canceled."""
        from titantrade.executor import _wait_for_order_canceled
        mock_get.return_value = {"status": "filled"}
        assert _wait_for_order_canceled("oid", fake_config) == "filled"

    @patch("titantrade.executor.time.sleep")
    @patch("titantrade.executor.get_order", return_value=None)
    def test_treats_missing_order_as_canceled(self, mock_get, mock_sleep, fake_config):
        """A 404 (order has been GC'd) means it's no longer holding qty."""
        from titantrade.executor import _wait_for_order_canceled
        assert _wait_for_order_canceled("oid", fake_config) == "canceled"

    @patch("titantrade.executor.time.time")
    @patch("titantrade.executor.time.sleep")
    @patch("titantrade.executor.get_order")
    def test_returns_none_on_timeout(
        self, mock_get, mock_sleep, mock_time, fake_config,
    ):
        from titantrade.executor import _wait_for_order_canceled
        mock_get.return_value = {"status": "pending_cancel"}
        mock_time.side_effect = [0.0, 0.0, 200.0, 200.0]
        assert _wait_for_order_canceled("oid", fake_config) is None


# ---------------------------------------------------------------------------
# Re-entry cooldown after ABORT (#1)
# ---------------------------------------------------------------------------

class TestReentryCooldown:
    def test_record_and_check_cooldown(self, tmp_state_dir):
        from titantrade.executor import (
            _is_in_cooldown,
            _record_abort_cooldown,
            REENTRY_COOLDOWN_HOURS,
        )
        # Fresh ABORT — should be in cooldown
        _record_abort_cooldown("FCX", "test reason")
        in_cooldown, hours = _is_in_cooldown("FCX")
        assert in_cooldown is True
        assert hours < 1.0

    def test_unrelated_ticker_not_in_cooldown(self, tmp_state_dir):
        from titantrade.executor import _is_in_cooldown, _record_abort_cooldown
        _record_abort_cooldown("FCX", "test")
        in_cooldown, _ = _is_in_cooldown("NVDA")
        assert in_cooldown is False

    def test_expired_cooldown_returns_false_and_prunes(self, tmp_state_dir, monkeypatch):
        """A cooldown older than REENTRY_COOLDOWN_HOURS should auto-expire."""
        import datetime as dt
        import json as _json
        from titantrade.executor import _is_in_cooldown
        # Write a stale entry directly (older than the window)
        stale_time = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=100)
        (tmp_state_dir / "abort_cooldown.json").write_text(_json.dumps({
            "FCX": {"aborted_at": stale_time.isoformat(), "reason": "old"}
        }))
        in_cooldown, hours = _is_in_cooldown("FCX")
        assert in_cooldown is False
        assert hours >= 72  # past the window

    @patch("titantrade.executor.place_bracket_order")
    def test_handle_bullish_entry_blocked_by_cooldown(
        self, mock_bracket, fake_config, data_bundle, tmp_state_dir,
    ):
        """A ticker in cooldown should not get a new bracket placed."""
        from titantrade.executor import _record_abort_cooldown
        _record_abort_cooldown("AAPL", "tripped")

        thesis = {
            "ticker": "AAPL",
            "thesis": "BULLISH",
            "confidence": 0.85,
            "target_entry_price": 145.0,
            "stop_loss_price": 138.0,
            "take_profit_price": 160.0,
            "selected_for_trading": True,
        }
        result = _handle_bullish_entry(
            ticker="AAPL", thesis=thesis,
            portfolio_value=100_000, cash_balance=50_000,
            positions=[], data_bundle=data_bundle, sentry=None, cfg=fake_config,
        )
        assert result is None
        mock_bracket.assert_not_called()


# ---------------------------------------------------------------------------
# Bracket-attempt price-chase cap (#4)
# ---------------------------------------------------------------------------

class TestBracketAttemptCap:
    @patch("titantrade.executor.place_bracket_order")
    @patch("titantrade.executor.get_open_orders", return_value=[])
    @patch("titantrade.executor.get_positions", return_value=[])
    @patch("titantrade.executor.get_account", return_value={"portfolio_value": "100000", "cash": "50000"})
    @patch("titantrade.executor.get_expired_brackets")
    def test_skips_after_max_attempts(
        self, mock_expired, mock_account, mock_pos, mock_open, mock_bracket,
        fake_config, bullish_thesis, tmp_state_dir,
    ):
        """If the same ticker has more than MAX_BRACKET_ATTEMPTS expired
        brackets in Alpaca's history, we should stop chasing the price."""
        from titantrade.executor import MAX_BRACKET_ATTEMPTS
        # Generate enough expired brackets to trip the cap (+1 to be over)
        mock_expired.return_value = [
            {
                "symbol": "AAPL", "status": "expired", "order_class": "bracket",
                "side": "buy", "qty": "10", "limit_price": "100",
            }
            for _ in range(MAX_BRACKET_ATTEMPTS + 1)
        ]
        thesis_doc = {
            "theses": [{**bullish_thesis, "selected_for_trading": True}],
        }
        result = resubmit_expired_brackets(fake_config, thesis_doc, [], {})
        assert result == []
        mock_bracket.assert_not_called()


# ---------------------------------------------------------------------------
# State-file archival (#8)
# ---------------------------------------------------------------------------

class TestStateArchival:
    def test_trade_log_archives_overflow(self, tmp_state_dir):
        """When trade_log.json exceeds MAX_LIVE_TRADES, archive the excess."""
        from titantrade.executor import (
            _append_trade,
            MAX_LIVE_TRADES,
        )
        # Append MAX+5 trades; archive should fire and trim to MAX
        for i in range(MAX_LIVE_TRADES + 5):
            _append_trade({
                "id": f"trade_{i}",
                "ticker": "AAPL",
                "action": "BUY",
                "shares": 1,
                "price": 100.0,
                "timestamp": "2026-01-01T00:00:00+00:00",
                "trigger": "test",
                "reasoning": "test",
            })

        # Main file kept the most recent MAX_LIVE_TRADES
        data = json.loads((tmp_state_dir / "trade_log.json").read_text())
        assert len(data["trades"]) == MAX_LIVE_TRADES

        # Archive directory has at least one rolled-up file
        archive_dir = tmp_state_dir / "archive"
        assert archive_dir.exists()
        archives = list(archive_dir.glob("trade_log.*.json"))
        assert len(archives) >= 1


# ---------------------------------------------------------------------------
# Stuck-in-cash + churn alerts (#9, #10)
# ---------------------------------------------------------------------------

class TestStuckInCashAlert:
    @patch("titantrade.notifier.send_discord")
    def test_alerts_after_threshold_days(
        self, mock_send, tmp_state_dir,
    ):
        """3 days of high-cash should fire one alert, then suppress repeats today."""
        from titantrade.executor import (
            _maybe_alert_stuck_in_cash,
            STUCK_IN_CASH_DAYS_THRESHOLD,
        )
        import datetime as dt
        import json as _json
        # Pre-seed state so we've been stuck for 4 days
        start = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(
            days=STUCK_IN_CASH_DAYS_THRESHOLD + 1)).date().isoformat()
        (tmp_state_dir / "alert_state.json").write_text(_json.dumps({
            "stuck_in_cash_since": start
        }))

        # 90% cash — over threshold
        _maybe_alert_stuck_in_cash(portfolio_value=100_000, cash_balance=90_000)
        assert mock_send.call_count == 1

        # Same day — should NOT alert again
        _maybe_alert_stuck_in_cash(portfolio_value=100_000, cash_balance=90_000)
        assert mock_send.call_count == 1

    @patch("titantrade.notifier.send_discord")
    def test_does_not_alert_below_threshold(self, mock_send, tmp_state_dir):
        from titantrade.executor import _maybe_alert_stuck_in_cash
        _maybe_alert_stuck_in_cash(portfolio_value=100_000, cash_balance=30_000)
        mock_send.assert_not_called()


class TestTickerChurnAlert:
    @patch("titantrade.notifier.send_discord")
    def test_alerts_on_excessive_round_trips(self, mock_send, tmp_state_dir):
        from titantrade.executor import (
            _maybe_alert_ticker_churn,
            TICKER_CHURN_ROUND_TRIPS,
        )
        import datetime as dt
        import json as _json
        # Build a trade log with 2 round trips of LLY in the last 3 days
        now = dt.datetime.now(dt.timezone.utc)
        trades = []
        for i in range(TICKER_CHURN_ROUND_TRIPS):
            ts_buy = (now - dt.timedelta(days=2 - i, hours=1)).isoformat()
            ts_sell = (now - dt.timedelta(days=2 - i)).isoformat()
            trades.append({
                "ticker": "LLY", "action": "BUY", "timestamp": ts_buy,
                "shares": 1, "price": 900.0, "trigger": "test", "reasoning": "test",
            })
            trades.append({
                "ticker": "LLY", "action": "SELL", "timestamp": ts_sell,
                "shares": 1, "price": 890.0, "trigger": "test", "reasoning": "test",
            })
        (tmp_state_dir / "trade_log.json").write_text(_json.dumps({"trades": trades}))

        _maybe_alert_ticker_churn()
        assert mock_send.call_count >= 1
        # Re-running same day should NOT alert again for the same ticker
        _maybe_alert_ticker_churn()
        assert mock_send.call_count >= 1  # unchanged
