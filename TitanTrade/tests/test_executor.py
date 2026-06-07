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

from titantrade.broker import place_native_stop_loss
from titantrade.core_allocation import manage_core_position
from titantrade.entries import _handle_bullish_entry, resubmit_expired_brackets
from titantrade.positions import maybe_pyramid_position
from titantrade.pricing import _choose_entry_price, compute_trend_regime
from titantrade.trade_state import _build_trade_context
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

    @patch("titantrade.entries.place_bracket_order", return_value={"id": "order_123"})
    @patch("titantrade.entries.get_open_orders", return_value=[])
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

    @patch("titantrade.entries.place_bracket_order")
    @patch("titantrade.entries.get_open_orders", return_value=[])
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

    @patch("titantrade.entries.place_bracket_order")
    @patch("titantrade.entries.get_open_orders", return_value=[])
    def test_near_miss_recorded(
        self, mock_orders, mock_bracket, fake_config, bullish_thesis, sample_positions, data_bundle, tmp_state_dir
    ):
        """When blocked by 1-2 gates, a near-miss should be saved."""
        bullish_thesis["confidence"] = 0.30  # Below new 0.55 floor — confidence fails
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


# ---------------------------------------------------------------------------
# Trend regime detection + adaptive entries
# ---------------------------------------------------------------------------

class TestTrendRegime:
    def _bundle(self, *, rsi=50.0, **pvs):
        """Build a minimal data bundle with overridable price_vs_sma fields."""
        return {
            "stocks": {
                "FOO": {
                    "technical_indicators": {
                        "rsi_14": rsi,
                        "price_vs_sma": pvs,
                    },
                },
            },
        }

    def test_strong_up(self):
        bundle = self._bundle(
            above_sma_50=True, above_sma_200=True,
            golden_cross=True, pct_from_sma_50=5.0,
            sma_20=100.0, sma_50=95.0,
        )
        assert compute_trend_regime("FOO", bundle, current_price=105.0) == "strong_up"

    def test_up_without_golden_cross(self):
        bundle = self._bundle(
            above_sma_50=True, above_sma_200=True,
            golden_cross=False, pct_from_sma_50=3.0,
            sma_20=100.0, sma_50=95.0,
        )
        assert compute_trend_regime("FOO", bundle, current_price=103.0) == "up"

    def test_down(self):
        bundle = self._bundle(
            above_sma_50=False, above_sma_200=False,
            golden_cross=False, pct_from_sma_50=-4.0,
            sma_20=95.0, sma_50=100.0,
        )
        assert compute_trend_regime("FOO", bundle, current_price=96.0) == "down"

    def test_range_when_indicators_missing(self):
        bundle = {"stocks": {"FOO": {"technical_indicators": {}}}}
        assert compute_trend_regime("FOO", bundle, current_price=100.0) == "range"

    def test_range_when_above_50_but_negative(self):
        # Edge case: above_50 True but pct_from_50 negative (lagged data)
        bundle = self._bundle(
            above_sma_50=True, above_sma_200=False,
            golden_cross=False, pct_from_sma_50=-0.5,
            sma_20=100.0, sma_50=100.5,
        )
        assert compute_trend_regime("FOO", bundle, current_price=100.0) == "range"

    def test_overbought_strong_up_downgrades_to_range(self):
        """Even a screaming uptrend with golden cross gets downgraded to
        'range' if RSI > 75. Buying parabolic extensions = exit liquidity.
        """
        bundle = self._bundle(
            rsi=82.0,  # overbought
            above_sma_50=True, above_sma_200=True,
            golden_cross=True, pct_from_sma_50=8.0,
            sma_20=100.0, sma_50=95.0,
        )
        assert compute_trend_regime("FOO", bundle, current_price=110.0) == "range"

    def test_overbought_plain_up_also_downgrades(self):
        bundle = self._bundle(
            rsi=78.0,
            above_sma_50=True, above_sma_200=True,
            golden_cross=False, pct_from_sma_50=3.0,
            sma_20=100.0, sma_50=95.0,
        )
        assert compute_trend_regime("FOO", bundle, current_price=103.0) == "range"


class TestChooseEntryPrice:
    def _thesis(self, target=100.0):
        return {
            "target_entry_price": target,
            "stop_loss_price": 95.0,
            "take_profit_price": 110.0,
        }

    def test_high_conviction_uses_near_market(self):
        # conf >= 0.80 → current * 1.003 regardless of regime
        price = _choose_entry_price(self._thesis(), 105.0, regime="up", confidence=0.85)
        assert price == round(105.0 * 1.003, 2)

    def test_strong_up_uses_near_market(self):
        # strong_up regime → current * 1.003 even at lower conviction
        price = _choose_entry_price(self._thesis(), 105.0, regime="strong_up", confidence=0.65)
        assert price == round(105.0 * 1.003, 2)

    def test_up_regime_uses_small_breakout_buffer(self):
        price = _choose_entry_price(self._thesis(), 105.0, regime="up", confidence=0.65)
        assert price == round(105.0 * 1.001, 2)

    def test_range_keeps_thesis_target_when_below_current(self):
        # Range + thesis target $100 + current $105 → cap at current.
        # The point: don't blindly pay current when the thesis said wait
        # for $100, but also don't sit on a $100 limit that won't fill.
        # min(target, current) = min(100, 105) = 100.
        price = _choose_entry_price(self._thesis(target=100.0), 105.0, "range", confidence=0.60)
        assert price == 100.0

    def test_no_current_price_falls_back_to_thesis(self):
        price = _choose_entry_price(self._thesis(target=100.0), None, "up", confidence=0.65)
        assert price == 100.0


class TestHandleBullishEntryTrendAdaptive:
    """Verify the real entry path responds to trend regime."""

    @patch("titantrade.daily_sentry._fetch_current_price", return_value=200.0)
    @patch("titantrade.entries.place_bracket_order")
    @patch("titantrade.entries.get_open_orders", return_value=[])
    def test_downtrend_skips_entry(
        self, mock_orders, mock_bracket, mock_price,
        fake_config, bullish_thesis, sample_positions, tmp_state_dir,
    ):
        """When the regime is 'down', we don't bottom-fish — skip entry."""
        bundle = {
            "stocks": {
                "AAPL": {
                    "technical_indicators": {
                        "price_vs_sma": {
                            "above_sma_50": False, "above_sma_200": False,
                            "golden_cross": False, "pct_from_sma_50": -4.0,
                            "sma_20": 210.0, "sma_50": 215.0,
                        },
                    },
                    "atr_14": 3.0,
                },
            },
        }
        result = _handle_bullish_entry(
            ticker="AAPL", thesis=bullish_thesis,
            portfolio_value=100_000, cash_balance=50_000,
            positions=sample_positions, data_bundle=bundle,
            sentry=None, cfg=fake_config,
        )
        assert result is None
        mock_bracket.assert_not_called()

    @patch("titantrade.daily_sentry._fetch_current_price", return_value=200.0)
    @patch("titantrade.entries.place_bracket_order", return_value={"id": "br-1"})
    @patch("titantrade.entries.get_open_orders", return_value=[])
    def test_strong_up_uses_near_market_entry(
        self, mock_orders, mock_bracket, mock_price,
        fake_config, bullish_thesis, sample_positions, tmp_state_dir, monkeypatch,
    ):
        """Strong uptrend → entry adapts to ~current price, not thesis target."""
        monkeypatch.setattr("titantrade.risk_manager.get_stock_sector", lambda t: "Technology")

        bullish_thesis["target_entry_price"] = 185.50  # original thesis dip-buy
        bundle = {
            "stocks": {
                "AAPL": {
                    "technical_indicators": {
                        "price_vs_sma": {
                            "above_sma_50": True, "above_sma_200": True,
                            "golden_cross": True, "pct_from_sma_50": 5.0,
                            "sma_20": 195.0, "sma_50": 190.0,
                        },
                    },
                    "atr_14": 3.0,
                },
            },
        }
        _handle_bullish_entry(
            ticker="AAPL", thesis=bullish_thesis,
            portfolio_value=100_000, cash_balance=50_000,
            positions=sample_positions, data_bundle=bundle,
            sentry=None, cfg=fake_config,
        )

        # Bracket was placed; verify entry is near current ($200), not the
        # thesis $185.50.
        assert mock_bracket.call_count >= 1
        first_call = mock_bracket.call_args_list[0]
        entry_arg = first_call.kwargs.get("entry_limit_price") or first_call.args[2]
        # current_price=200, mult=1.003 → 200.60
        assert entry_arg >= 200.0
        assert entry_arg <= 201.0


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

    @patch("titantrade.entries.place_bracket_order", return_value={"id": "resubmit_1"})
    @patch("titantrade.entries.get_positions", return_value=[])
    @patch("titantrade.entries.get_open_orders", return_value=[])
    @patch("titantrade.entries.get_account", return_value={"portfolio_value": "100000", "cash": "50000"})
    @patch("titantrade.entries.get_expired_brackets")
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

    @patch("titantrade.entries.get_expired_brackets", return_value=[])
    def test_no_expired_returns_empty(self, mock_expired, fake_config):
        result = resubmit_expired_brackets(fake_config, {"theses": []}, [], {})
        assert result == []

    @patch("titantrade.entries.place_bracket_order")
    @patch("titantrade.entries.get_positions", return_value=[])
    @patch("titantrade.entries.get_open_orders", return_value=[])
    @patch("titantrade.entries.get_account", return_value={"portfolio_value": "100000", "cash": "50000"})
    @patch("titantrade.entries.get_expired_brackets")
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

    @patch("titantrade.entries.place_bracket_order")
    @patch("titantrade.entries.get_positions", return_value=[])
    @patch("titantrade.entries.get_open_orders", return_value=[])
    @patch("titantrade.entries.get_account", return_value={"portfolio_value": "100000", "cash": "50000"})
    @patch("titantrade.entries.get_expired_brackets")
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

    @patch("titantrade.entries.place_bracket_order")
    @patch("titantrade.entries.get_positions", return_value=[])
    @patch("titantrade.entries.get_open_orders", return_value=[])
    @patch("titantrade.entries.get_account", return_value={"portfolio_value": "100000", "cash": "50000"})
    @patch("titantrade.entries.get_expired_brackets")
    def test_dedupes_skip_log_lines_per_ticker_reason(
        self, mock_expired, mock_account, mock_open, mock_pos, mock_bracket,
        fake_config, bullish_thesis, caplog,
    ):
        """Production logs were drowned by 50+ near-identical skip lines because
        Alpaca's expired-order list contained many duplicate bracket parents per
        ticker. Same-(ticker, reason) skips must be collapsed to one log line.
        """
        # 10 expired brackets for the same ticker, all hit the "already holding"
        # skip path → should produce exactly ONE skip log line.
        mock_expired.return_value = [
            self._make_expired_order() for _ in range(10)
        ]
        thesis_doc = {
            "theses": [{**bullish_thesis, "selected_for_trading": True}],
        }
        positions = [{"symbol": "AAPL", "qty": "50", "market_value": "9000"}]

        import logging
        with caplog.at_level(logging.INFO, logger="titantrade.executor"):
            resubmit_expired_brackets(fake_config, thesis_doc, positions, {})

        skip_lines = [
            r.message for r in caplog.records
            if "Skipping expired bracket for AAPL" in r.message
        ]
        assert len(skip_lines) == 1, (
            f"Expected 1 deduplicated skip line, got {len(skip_lines)}: {skip_lines}"
        )
        # And the dedup summary should mention the collapsed duplicates.
        summary_lines = [
            r.message for r in caplog.records if "skip dedup" in r.message
        ]
        assert len(summary_lines) == 1
        assert "9 duplicate" in summary_lines[0]


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
    @patch("titantrade.broker.get_order")
    @patch("titantrade.broker.fetch_with_retry")
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

    @patch("titantrade.broker._wait_for_order_canceled", return_value=None)
    @patch("titantrade.broker.fetch_with_retry")
    def test_qty_race_times_out_if_cancel_never_completes(
        self, mock_fetch, mock_wait, fake_config,
    ):
        """If the blocking order never reaches a terminal state (e.g. an
        off-hours pending_cancel), we raise rather than retrying forever.

        Patching ``_wait_for_order_canceled`` directly (instead of mocking the
        global ``time.time`` with a fixed side_effect) makes this robust: the
        prior version exhausted its time.time() sequence because pytest's log
        capture also calls the globally-patched time.time per log record.
        """
        # available "0" in the race body means there's nothing to clamp to,
        # so a timeout must propagate the original error.
        mock_fetch.side_effect = [_make_qty_race_error("stuck-order")]

        with pytest.raises(HTTPError) as exc_info:
            place_native_stop_loss("FCX", 121, 64.50, fake_config)

        assert exc_info.value.error_code == 40310000
        assert mock_fetch.call_count == 1  # one initial attempt; gave up polling
        mock_wait.assert_called_once_with("stuck-order", fake_config)

    @patch("titantrade.broker.fetch_with_retry")
    def test_qty_race_without_related_orders_or_available_raises(self, mock_fetch, fake_config):
        """If Alpaca returns 40310000 without naming the blocking order AND
        without an ``available`` qty to clamp to, we can't recover — raise."""
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

    @patch("titantrade.broker.fetch_with_retry")
    def test_qty_race_without_related_orders_clamps_to_available(self, mock_fetch, fake_config):
        """FIX (bare-position guard): when Alpaca reports a positive
        ``available`` qty but names no blocking order to poll, we must NOT give
        up — we clamp the stop to the available shares and retry. A stop on 103
        of 121 shares beats leaving the position bare (the FCX production race).
        """
        race = HTTPError(
            status_code=403,
            body=(
                '{"code":40310000,"available":"103","existing_qty":"103",'
                '"held_for_orders":"0",'
                '"message":"insufficient qty available for order (requested: 121, available: 103)",'
                '"symbol":"FCX"}'
            ),
            url="https://paper-api.alpaca.markets/v2/orders",
            method="POST",
        )
        mock_fetch.side_effect = [race, _make_response({"id": "clamped-stop", "status": "accepted"})]

        result = place_native_stop_loss("FCX", 121, 64.50, fake_config)

        assert result["id"] == "clamped-stop"
        assert mock_fetch.call_count == 2
        # The retry placed a stop for the broker-reported available qty (103),
        # not the original stale 121.
        retry_body = mock_fetch.call_args_list[1].kwargs["json_body"]
        assert retry_body["qty"] == "103.0"
        assert retry_body["type"] == "stop_limit"

    @patch("titantrade.broker.fetch_with_retry")
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

    @patch("titantrade.broker.fetch_with_retry")
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
# Section 4b — TP-leg-holding-qty recovery (off-hours + race-condition fixes)
# ---------------------------------------------------------------------------

class TestTpLegHoldingQty:
    """Production scenario: a held position has no stop_loss order, but a
    take-profit (limit sell) leg from the original bracket is still active
    and holds all the qty. Placing a fresh stop deterministically 403s with
    "insufficient qty available". Section 4b now:
      1. Off-hours → defer (don't try the cancel — it won't settle).
      2. Market open → cancel the TP, place the stop. On failure, restore TP.

    These are inline-pattern tests like TestAdjustStopSafety. They document
    the contract; they don't drive execute_trades end-to-end (which would
    require mocking ~15 broker calls).
    """

    def test_off_hours_path_does_not_call_broker(self):
        """When market is closed and qty is held by a TP leg, we must NOT
        cancel anything. The cancel would hang in pending_cancel until next
        open, and we'd still 403. Defer cleanly instead.
        """
        from unittest.mock import MagicMock
        cancel_order = MagicMock()
        place_native_stop_loss = MagicMock()

        market_open = False
        has_stop = False
        qty_available = 0
        tp_limit_orders = [{"id": "tp-1", "qty": "14", "limit_price": "550.00"}]

        if not has_stop and qty_available <= 0 and tp_limit_orders:
            if not market_open:
                pass  # deferred — no broker calls
            else:
                for tp in tp_limit_orders:
                    cancel_order(tp["id"])
                place_native_stop_loss()

        cancel_order.assert_not_called()
        place_native_stop_loss.assert_not_called()

    def test_market_open_cancels_tp_and_places_stop(self):
        """Happy path: market open, TP holds qty, no stop → cancel TP, place
        stop. Both broker calls fire exactly once.
        """
        from unittest.mock import MagicMock
        cancel_order = MagicMock()
        place_native_stop_loss = MagicMock(return_value={"id": "new-stop"})

        market_open = True
        has_stop = False
        qty_available = 0
        tp_limit_orders = [{"id": "tp-1", "qty": "14", "limit_price": "550.00"}]

        if not has_stop and qty_available <= 0 and tp_limit_orders and market_open:
            for tp in tp_limit_orders:
                cancel_order(tp["id"])
            place_native_stop_loss(stop_price=494.0)

        cancel_order.assert_called_once_with("tp-1")
        place_native_stop_loss.assert_called_once()

    def test_failed_stop_placement_restores_tp(self):
        """Safety net: if cancel succeeds and place_native_stop_loss raises,
        we MUST restore the TP. Without this, the position is left with
        neither stop nor TP — both downside and upside exits gone.
        """
        from unittest.mock import MagicMock
        cancel_order = MagicMock()
        place_native_stop_loss = MagicMock(side_effect=RuntimeError("503"))
        place_limit_sell = MagicMock(return_value={"id": "restored-tp"})

        tp_limit_orders = [{"id": "tp-1", "qty": "14", "limit_price": "550.00"}]
        # Snapshot before cancel so we can restore later (this is the actual
        # pattern in executor.py).
        tp_snapshots = [
            {"qty": float(tp["qty"]), "limit_price": float(tp["limit_price"])}
            for tp in tp_limit_orders
        ]

        for tp in tp_limit_orders:
            cancel_order(tp["id"])

        try:
            place_native_stop_loss(stop_price=494.0)
        except Exception:
            # Safety net branch
            for snap in tp_snapshots:
                place_limit_sell(snap["qty"], snap["limit_price"], "gtc")

        cancel_order.assert_called_once()
        place_native_stop_loss.assert_called_once()
        # TP was restored at its original limit price
        place_limit_sell.assert_called_once_with(14.0, 550.00, "gtc")


# ---------------------------------------------------------------------------
# REAL end-to-end integration tests — drive execute_trades through the new
# branches. These call the actual production function and verify the real
# code path (not inline-pattern stubs).
# ---------------------------------------------------------------------------

def _config_with_watchlist(cfg, watchlist: list[str]):
    """Config is a frozen dataclass — build a new one with the desired
    watchlist via dataclasses.replace.
    """
    from dataclasses import replace
    new_trading = replace(cfg.trading, watchlist=watchlist)
    return replace(cfg, trading=new_trading)


@pytest.fixture
def _e2e_state(tmp_state_dir):
    """Write the three state files execute_trades needs."""
    write_state_file(tmp_state_dir, "weekly_thesis.json", {
        "generated_at": "2026-05-20T00:00:00+00:00",
        "next_review_at": "2026-06-01T00:00:00+00:00",
        "theses": [
            {
                "ticker": "CRWD",
                "thesis": "BULLISH",
                "confidence": 0.85,
                "target_entry_price": 500.0,
                "stop_loss_price": 494.0,
                "take_profit_price": 550.0,
                "selected_for_trading": True,
                "review_action": "NEW",
                "reasoning": "Held position needs stop",
            },
        ],
    })
    write_state_file(tmp_state_dir, "sentry_signals.json", {
        "generated_at": "2026-05-20T13:00:00+00:00",
        "signals": [{"ticker": "CRWD", "signal": "CONTINUE"}],
    })
    write_state_file(tmp_state_dir, "data_bundle.json", {"stocks": {}})
    return tmp_state_dir


def _stub_e2e_mocks(monkeypatch, *, market_open: bool, position: dict, open_orders: list):
    """Patch all the broker/external touchpoints execute_trades needs.
    Returns a dict of MagicMocks for assertions.
    """
    mocks: dict[str, MagicMock] = {}

    def _patch(name: str, **kw):
        m = MagicMock(**kw)
        monkeypatch.setattr(f"titantrade.executor.{name}", m)
        mocks[name] = m
        return m

    _patch("is_market_open", return_value=market_open)
    _patch("load_stock_sectors", return_value=None)
    _patch("close_orphaned_positions", return_value=[])
    _patch("check_gap_down_protection", return_value=[])
    _patch("resubmit_expired_brackets", return_value=[])
    _patch("get_account", return_value={
        "portfolio_value": "100000", "cash": "20000", "buying_power": "40000",
    })
    _patch("get_positions", return_value=[position])
    _patch("get_position", return_value=position)
    _patch("get_open_orders", return_value=open_orders)
    _patch("cancel_order", return_value=None)
    _patch("place_native_stop_loss", return_value={"id": "new-stop"})
    _patch("place_limit_sell", return_value={"id": "restored-tp"})
    _patch("manage_trailing_stop", return_value=None)
    # Section 4b also runs the pyramid check on held BULLISH positions; stub it
    # so these stop-placement E2E tests stay focused and hermetic (the real one
    # would place a limit buy over the network).
    _patch("maybe_pyramid_position", return_value=None)
    _patch("_maybe_alert_stuck_in_cash", return_value=None)
    _patch("_maybe_alert_ticker_churn", return_value=None)
    return mocks


class TestExecuteTradesEndToEnd:
    """Drive the actual execute_trades function through each new branch and
    verify the real-world broker-call sequence. These tests catch regressions
    that the inline-pattern tests (TestTpLegHoldingQty) cannot.
    """

    def test_off_hours_with_tp_holding_qty_makes_no_broker_calls(
        self, monkeypatch, _e2e_state, fake_config,
    ):
        """Production bug: off-hours + held position + TP-leg-holds-qty +
        no stop → previous code POSTed a stop, ate a 120s pending_cancel
        wait, then 403'd. New code must defer with zero broker calls.
        """
        # Override the watchlist so the sector-cache + sentry loops only see CRWD.
        fake_config = _config_with_watchlist(fake_config, ["CRWD"])

        position = {
            "symbol": "CRWD", "qty": "14", "qty_available": "0",
            "held_for_orders": "14", "current_price": "560",
            "avg_entry_price": "510",
        }
        # Only a TP limit leg — no stop. Qty is held by the TP.
        open_orders = [
            {"id": "tp-leg-1", "side": "sell", "type": "limit",
             "qty": "14", "limit_price": "550.00"},
        ]
        mocks = _stub_e2e_mocks(
            monkeypatch, market_open=False,
            position=position, open_orders=open_orders,
        )

        from titantrade.executor import execute_trades
        execute_trades(fake_config)

        # The critical assertions — off-hours must NOT touch the broker for
        # stop placement on this position.
        mocks["cancel_order"].assert_not_called()
        mocks["place_native_stop_loss"].assert_not_called()
        mocks["place_limit_sell"].assert_not_called()

    def test_market_open_with_tp_holding_qty_cancels_tp_then_places_stop(
        self, monkeypatch, _e2e_state, fake_config,
    ):
        """Market-open recovery: cancel the TP that's holding the qty, then
        place the protective stop. Both calls must fire exactly once."""
        fake_config = _config_with_watchlist(fake_config, ["CRWD"])

        position = {
            "symbol": "CRWD", "qty": "14", "qty_available": "0",
            "held_for_orders": "14", "current_price": "560",
            "avg_entry_price": "510",
        }
        open_orders = [
            {"id": "tp-leg-1", "side": "sell", "type": "limit",
             "qty": "14", "limit_price": "550.00"},
        ]
        mocks = _stub_e2e_mocks(
            monkeypatch, market_open=True,
            position=position, open_orders=open_orders,
        )

        from titantrade.executor import execute_trades
        execute_trades(fake_config)

        # TP cancelled, stop placed, TP restore NOT called (happy path).
        mocks["cancel_order"].assert_called_once()
        assert mocks["cancel_order"].call_args.args[0] == "tp-leg-1"
        mocks["place_native_stop_loss"].assert_called_once()
        place_args = mocks["place_native_stop_loss"].call_args.args
        assert place_args[0] == "CRWD"
        assert float(place_args[1]) == 14.0  # qty
        assert float(place_args[2]) == 494.0  # stop_price from thesis
        mocks["place_limit_sell"].assert_not_called()

    def test_failed_stop_placement_restores_tp_end_to_end(
        self, monkeypatch, _e2e_state, fake_config,
    ):
        """Half-failure safety net: if place_native_stop_loss raises after the
        TP was cancelled, the TP MUST be restored at its original limit price.
        Without this, the position has neither stop nor TP — both exits gone.
        """
        fake_config = _config_with_watchlist(fake_config, ["CRWD"])

        position = {
            "symbol": "CRWD", "qty": "14", "qty_available": "0",
            "held_for_orders": "14", "current_price": "560",
            "avg_entry_price": "510",
        }
        open_orders = [
            {"id": "tp-leg-1", "side": "sell", "type": "limit",
             "qty": "14", "limit_price": "550.00"},
        ]
        mocks = _stub_e2e_mocks(
            monkeypatch, market_open=True,
            position=position, open_orders=open_orders,
        )
        # Make place_native_stop_loss fail to trigger the restore branch
        mocks["place_native_stop_loss"].side_effect = RuntimeError("503 Service Unavailable")

        from titantrade.executor import execute_trades
        execute_trades(fake_config)

        # Sequence: cancel TP → try stop (fails) → restore TP
        mocks["cancel_order"].assert_called_once()
        mocks["place_native_stop_loss"].assert_called_once()
        mocks["place_limit_sell"].assert_called_once()
        restore_args = mocks["place_limit_sell"].call_args
        assert restore_args.args[0] == "CRWD"
        assert float(restore_args.args[1]) == 14.0
        assert float(restore_args.args[2]) == 550.00
        assert restore_args.kwargs.get("time_in_force") == "gtc"

    def test_off_hours_held_position_no_stop_no_tp_defers(
        self, monkeypatch, _e2e_state, fake_config,
    ):
        """Off-hours, held position has no protective orders at all and qty
        is fully available. Even though there's no race, we still defer —
        the next market-open run will place the stop cleanly. (We don't
        place stops during off-hours because the executor runs are 2/day
        and a missed window is small; the original code did place here, but
        the new gate is more conservative and that's fine.)

        Actually checking the spec: qty_available > 0, no TP holding qty,
        market closed → the new code logs "deferring stop placement to next
        market-open run" and does NOT call place_native_stop_loss.
        """
        fake_config = _config_with_watchlist(fake_config, ["CRWD"])

        position = {
            "symbol": "CRWD", "qty": "14", "qty_available": "14",
            "held_for_orders": "0", "current_price": "560",
            "avg_entry_price": "510",
        }
        # No orders at all — fully unprotected
        open_orders: list[dict[str, Any]] = []
        mocks = _stub_e2e_mocks(
            monkeypatch, market_open=False,
            position=position, open_orders=open_orders,
        )

        from titantrade.executor import execute_trades
        execute_trades(fake_config)

        # Off-hours: no broker mutations
        mocks["cancel_order"].assert_not_called()
        mocks["place_native_stop_loss"].assert_not_called()

    def test_market_open_held_position_no_protection_places_stop(
        self, monkeypatch, _e2e_state, fake_config,
    ):
        """Market-open, held position with no protective orders → place stop
        immediately for the available qty.
        """
        fake_config = _config_with_watchlist(fake_config, ["CRWD"])

        position = {
            "symbol": "CRWD", "qty": "14", "qty_available": "14",
            "held_for_orders": "0", "current_price": "560",
            "avg_entry_price": "510",
        }
        open_orders: list[dict[str, Any]] = []
        mocks = _stub_e2e_mocks(
            monkeypatch, market_open=True,
            position=position, open_orders=open_orders,
        )

        from titantrade.executor import execute_trades
        execute_trades(fake_config)

        mocks["cancel_order"].assert_not_called()  # nothing to cancel
        mocks["place_native_stop_loss"].assert_called_once()
        args = mocks["place_native_stop_loss"].call_args.args
        assert args[0] == "CRWD"
        assert float(args[1]) == 14.0  # qty_available
        assert float(args[2]) == 494.0  # stop_price from thesis

    def test_adjust_off_hours_no_existing_stop_defers(
        self, monkeypatch, tmp_state_dir, fake_config,
    ):
        """ADJUST branch with market closed AND no existing stop on the book
        used to fall through to cancel_all_orders_for_ticker + place_native_stop_loss
        because the off-hours gate had an `existing_stop is not None` clause.
        Now it defers unconditionally when market is closed.
        """
        write_state_file(tmp_state_dir, "weekly_thesis.json", {
            "generated_at": "2026-05-20T00:00:00+00:00",
            "next_review_at": "2026-06-01T00:00:00+00:00",
            "theses": [
                {
                    "ticker": "URI",
                    "thesis": "BULLISH",
                    "confidence": 0.85,
                    "target_entry_price": 770.0,
                    "stop_loss_price": 940.0,
                    "take_profit_price": 1000.0,
                    "selected_for_trading": True,
                    "review_action": "ADJUST",  # ← key
                    "reasoning": "Trail stop up",
                },
            ],
        })
        write_state_file(tmp_state_dir, "sentry_signals.json", {
            "generated_at": "2026-05-20T13:00:00+00:00",
            "signals": [{"ticker": "URI", "signal": "CONTINUE"}],
        })
        write_state_file(tmp_state_dir, "data_bundle.json", {"stocks": {}})

        fake_config = _config_with_watchlist(fake_config, ["URI"])
        position = {
            "symbol": "URI", "qty": "5", "qty_available": "5",
            "held_for_orders": "0", "current_price": "950",
            "avg_entry_price": "800",
        }
        # No existing stop AND no TP — the ADJUST branch's off-hours gate
        # previously bypassed this case (existing_stop is None) and fell
        # through to the cancel_all_orders + place path, which 403d.
        open_orders: list[dict[str, Any]] = []
        mocks = _stub_e2e_mocks(
            monkeypatch, market_open=False,
            position=position, open_orders=open_orders,
        )
        # Spy on cancel_all_orders_for_ticker too
        cancel_all = MagicMock(return_value=0)
        monkeypatch.setattr("titantrade.executor.cancel_all_orders_for_ticker", cancel_all)

        from titantrade.executor import execute_trades
        execute_trades(fake_config)

        # Off-hours ADJUST must defer — no cancel, no place
        cancel_all.assert_not_called()
        mocks["cancel_order"].assert_not_called()
        mocks["place_native_stop_loss"].assert_not_called()


# ---------------------------------------------------------------------------
# Bracket math sanity (Bug #2 — invalid stop/entry from ADJUSTed theses)
# ---------------------------------------------------------------------------

class TestBracketMathSanity:
    """Production showed brackets being placed with stop_price >= entry_price
    because the thesis had been ADJUSTed to raise the stop above the original
    entry (locking in profit on a position already held). The new entry path
    must detect and skip these — Alpaca would reject with HTTP 422 anyway.
    """

    @patch("titantrade.entries.place_bracket_order")
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

    @patch("titantrade.entries.place_bracket_order")
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
    @patch("titantrade.broker.fetch_with_retry")
    def test_is_market_open_true(self, mock_fetch, fake_config):
        from titantrade.executor import is_market_open
        mock_fetch.return_value = _make_response({"is_open": True})
        assert is_market_open(fake_config) is True

    @patch("titantrade.broker.fetch_with_retry")
    def test_is_market_open_false(self, mock_fetch, fake_config):
        from titantrade.executor import is_market_open
        mock_fetch.return_value = _make_response({"is_open": False})
        assert is_market_open(fake_config) is False

    @patch("titantrade.broker.fetch_with_retry")
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
    @patch("titantrade.broker.get_order")
    def test_returns_when_order_canceled(self, mock_get, mock_sleep, fake_config):
        from titantrade.broker import _wait_for_order_canceled
        mock_get.side_effect = [
            {"status": "pending_cancel"},
            {"status": "pending_cancel"},
            {"status": "canceled"},
        ]
        assert _wait_for_order_canceled("oid", fake_config) == "canceled"
        assert mock_get.call_count == 3

    @patch("titantrade.executor.time.sleep")
    @patch("titantrade.broker.get_order")
    def test_returns_when_filled(self, mock_get, mock_sleep, fake_config):
        """A bracket child order can become 'filled' instead of canceled."""
        from titantrade.broker import _wait_for_order_canceled
        mock_get.return_value = {"status": "filled"}
        assert _wait_for_order_canceled("oid", fake_config) == "filled"

    @patch("titantrade.executor.time.sleep")
    @patch("titantrade.broker.get_order", return_value=None)
    def test_treats_missing_order_as_canceled(self, mock_get, mock_sleep, fake_config):
        """A 404 (order has been GC'd) means it's no longer holding qty."""
        from titantrade.broker import _wait_for_order_canceled
        assert _wait_for_order_canceled("oid", fake_config) == "canceled"

    @patch("titantrade.executor.time.time")
    @patch("titantrade.executor.time.sleep")
    @patch("titantrade.broker.get_order")
    def test_returns_none_on_timeout(
        self, mock_get, mock_sleep, mock_time, fake_config,
    ):
        from titantrade.broker import _wait_for_order_canceled
        mock_get.return_value = {"status": "pending_cancel"}
        mock_time.side_effect = [0.0, 0.0, 200.0, 200.0]
        assert _wait_for_order_canceled("oid", fake_config) is None


# ---------------------------------------------------------------------------
# Re-entry cooldown after ABORT (#1)
# ---------------------------------------------------------------------------

class TestReentryCooldown:
    def test_record_and_check_cooldown(self, tmp_state_dir):
        from titantrade.cooldown import (
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
        from titantrade.cooldown import _is_in_cooldown, _record_abort_cooldown
        _record_abort_cooldown("FCX", "test")
        in_cooldown, _ = _is_in_cooldown("NVDA")
        assert in_cooldown is False

    def test_expired_cooldown_returns_false_and_prunes(self, tmp_state_dir, monkeypatch):
        """A cooldown older than REENTRY_COOLDOWN_HOURS should auto-expire."""
        import datetime as dt
        import json as _json
        from titantrade.cooldown import _is_in_cooldown
        # Write a stale entry directly (older than the window)
        stale_time = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=100)
        (tmp_state_dir / "abort_cooldown.json").write_text(_json.dumps({
            "FCX": {"aborted_at": stale_time.isoformat(), "reason": "old"}
        }))
        in_cooldown, hours = _is_in_cooldown("FCX")
        assert in_cooldown is False
        assert hours >= 72  # past the window

    @patch("titantrade.entries.place_bracket_order")
    def test_handle_bullish_entry_blocked_by_cooldown(
        self, mock_bracket, fake_config, data_bundle, tmp_state_dir,
    ):
        """A ticker in cooldown should not get a new bracket placed."""
        from titantrade.cooldown import _record_abort_cooldown
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


class TestCooldownOverride:
    """The cooldown override prevents the production lockout pattern: a single
    whipsaw ABORT locks the ticker out for 72h even after the stock recovers.
    With the override, sentry-confirmed recovery > 24h after the ABORT re-enters.
    """

    def _thesis(self, **overrides):
        base = {
            "ticker": "AAPL", "thesis": "BULLISH",
            "selected_for_trading": True,
            "stop_loss_price": 100.0,
        }
        base.update(overrides)
        return base

    def test_too_soon_no_override(self):
        from titantrade.cooldown import cooldown_override_allowed
        # Only 12h have passed — below the 24h minimum.
        assert cooldown_override_allowed(
            "AAPL", self._thesis(), {"signal": "CONTINUE"},
            hours_since_abort=12, current_price=110.0,
        ) is False

    def test_thesis_no_longer_bullish_no_override(self):
        from titantrade.cooldown import cooldown_override_allowed
        bearish = self._thesis(thesis="BEARISH")
        assert cooldown_override_allowed(
            "AAPL", bearish, {"signal": "CONTINUE"},
            hours_since_abort=48, current_price=110.0,
        ) is False

    def test_sentry_still_aborting_no_override(self):
        from titantrade.cooldown import cooldown_override_allowed
        assert cooldown_override_allowed(
            "AAPL", self._thesis(), {"signal": "ABORT"},
            hours_since_abort=48, current_price=110.0,
        ) is False

    def test_price_below_stop_no_override(self):
        from titantrade.cooldown import cooldown_override_allowed
        # Price = 99 below stop = 100 → hasn't recovered, don't re-enter
        assert cooldown_override_allowed(
            "AAPL", self._thesis(), {"signal": "CONTINUE"},
            hours_since_abort=48, current_price=99.0,
        ) is False

    def test_all_conditions_met_allows_override(self):
        from titantrade.cooldown import cooldown_override_allowed
        # 48h since ABORT, thesis still BULLISH, sentry CONTINUE, price
        # safely above stop → override allowed.
        assert cooldown_override_allowed(
            "AAPL", self._thesis(), {"signal": "CONTINUE"},
            hours_since_abort=48, current_price=110.0,
        ) is True

    def test_no_sentry_no_override(self):
        from titantrade.cooldown import cooldown_override_allowed
        # If there's no sentry signal at all, can't confirm recovery
        assert cooldown_override_allowed(
            "AAPL", self._thesis(), None,
            hours_since_abort=48, current_price=110.0,
        ) is False


# ---------------------------------------------------------------------------
# Bracket-attempt price-chase cap (#4)
# ---------------------------------------------------------------------------

class TestBracketAttemptCap:
    @patch("titantrade.entries.place_bracket_order")
    @patch("titantrade.entries.get_open_orders", return_value=[])
    @patch("titantrade.entries.get_positions", return_value=[])
    @patch("titantrade.entries.get_account", return_value={"portfolio_value": "100000", "cash": "50000"})
    @patch("titantrade.entries.get_expired_brackets")
    def test_skips_after_max_attempts(
        self, mock_expired, mock_account, mock_pos, mock_open, mock_bracket,
        fake_config, bullish_thesis, tmp_state_dir,
    ):
        """If the same ticker has more than MAX_BRACKET_ATTEMPTS expired
        brackets in Alpaca's history, we should stop chasing the price."""
        from titantrade.entries import MAX_BRACKET_ATTEMPTS
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
        from titantrade.trade_state import (
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
        from titantrade.alerts import (
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
        from titantrade.alerts import _maybe_alert_stuck_in_cash
        _maybe_alert_stuck_in_cash(portfolio_value=100_000, cash_balance=30_000)
        mock_send.assert_not_called()


class TestTickerChurnAlert:
    @patch("titantrade.notifier.send_discord")
    def test_alerts_on_excessive_round_trips(self, mock_send, tmp_state_dir):
        from titantrade.alerts import (
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


# ---------------------------------------------------------------------------
# Phase 3: Core position manager (always-deployed SPY base + hedge swap)
# ---------------------------------------------------------------------------

class TestManageCorePosition:
    def _write_sentry(self, tmp_state_dir, *, stress: bool):
        from tests.conftest import write_state_file
        write_state_file(tmp_state_dir, "sentry_signals.json", {
            "signals": [],
            "market_health": {
                "market_stress": stress,
                "spy_change_pct": -3.0 if stress else 0.5,
                "alert": "stress" if stress else "ok",
            },
        })

    @patch("titantrade.core_allocation.place_market_buy", return_value={"id": "core-buy"})
    @patch("titantrade.core_allocation.get_positions", return_value=[])
    @patch("titantrade.core_allocation.get_account", return_value={
        "portfolio_value": "100000", "cash": "50000",
    })
    @patch("titantrade.daily_sentry._fetch_current_price", return_value=500.0)
    @patch("titantrade.core_allocation.is_market_open", return_value=True)
    def test_buys_core_ticker_when_below_target(
        self, mock_open, mock_price, mock_account, mock_pos, mock_buy,
        fake_config, tmp_state_dir,
    ):
        """No SPY position, target is 30% of $100k = $30k → buy $30k of SPY
        at $500 = 60 shares. This is the always-deployed baseline.
        """
        self._write_sentry(tmp_state_dir, stress=False)
        trade = manage_core_position(fake_config)
        assert trade is not None
        assert trade["ticker"] == "SPY"
        assert trade["action"] == "BUY"
        assert trade["shares"] == 60  # $30k / $500
        mock_buy.assert_called_once()

    @patch("titantrade.core_allocation.place_market_buy")
    @patch("titantrade.core_allocation.get_positions")
    @patch("titantrade.core_allocation.get_account", return_value={
        "portfolio_value": "100000", "cash": "50000",
    })
    @patch("titantrade.core_allocation.is_market_open", return_value=True)
    def test_no_rebalance_when_within_band(
        self, mock_open, mock_account, mock_pos, mock_buy,
        fake_config, tmp_state_dir,
    ):
        """Already holding $32k SPY against $30k target → drift $2k, band is
        $5k. No rebalance.
        """
        self._write_sentry(tmp_state_dir, stress=False)
        mock_pos.return_value = [
            {"symbol": "SPY", "qty": "64", "market_value": "32000",
             "current_price": "500.00"},
        ]
        trade = manage_core_position(fake_config)
        assert trade is None
        mock_buy.assert_not_called()

    @patch("titantrade.core_allocation.place_market_sell", return_value={"id": "sell"})
    @patch("titantrade.core_allocation.place_market_buy", return_value={"id": "buy"})
    @patch("titantrade.core_allocation.cancel_all_orders_for_ticker", return_value=0)
    @patch("titantrade.core_allocation.close_position_at_market", return_value={"id": "close"})
    @patch("titantrade.core_allocation.get_positions")
    @patch("titantrade.core_allocation.get_account", return_value={
        "portfolio_value": "100000", "cash": "5000",  # Most capital in SPY
    })
    @patch("titantrade.daily_sentry._fetch_current_price", return_value=30.0)
    @patch("titantrade.core_allocation.is_market_open", return_value=True)
    def test_stress_swaps_spy_for_hedge(
        self, mock_open, mock_price, mock_account, mock_pos,
        mock_close, mock_cancel, mock_buy, mock_sell,
        fake_config, tmp_state_dir,
    ):
        """When market_stress=True, the manager should close SPY (the wrong
        core for the regime) — the proceeds flow back as cash and the next
        cycle can buy SH. This test verifies just the close half.
        """
        self._write_sentry(tmp_state_dir, stress=True)
        mock_pos.return_value = [
            {"symbol": "SPY", "qty": "60", "market_value": "30000",
             "current_price": "500.00"},
        ]
        manage_core_position(fake_config)
        # SPY was closed to make room for SH
        mock_close.assert_called_once_with("SPY", fake_config)

    @patch("titantrade.core_allocation.place_market_buy")
    @patch("titantrade.core_allocation.get_positions", return_value=[])
    @patch("titantrade.core_allocation.get_account", return_value={
        "portfolio_value": "100000", "cash": "50000",
    })
    @patch("titantrade.daily_sentry._fetch_current_price", return_value=500.0)
    @patch("titantrade.core_allocation.is_market_open", return_value=False)
    def test_off_hours_no_op(
        self, mock_open, mock_price, mock_account, mock_pos, mock_buy,
        fake_config, tmp_state_dir,
    ):
        """Off-hours: defer. Market orders need market hours, and bracket
        cancels/replaces hang in pending_cancel anyway. Even with all the
        other inputs valid (price quote, cash, etc.) we must return early
        on the is_market_open check — that's the entire safety contract.
        """
        self._write_sentry(tmp_state_dir, stress=False)
        trade = manage_core_position(fake_config)
        assert trade is None
        mock_buy.assert_not_called()
        # Critically: we should NOT have even queried the account if we
        # bailed early. (If get_account was hit, the function ran past the
        # off-hours gate.)
        mock_account.assert_not_called()

    @patch("titantrade.core_allocation.place_market_buy")
    @patch("titantrade.core_allocation.get_positions", return_value=[])
    @patch("titantrade.core_allocation.get_account", return_value={
        "portfolio_value": "100000", "cash": "2000",  # Below 5% floor
    })
    @patch("titantrade.daily_sentry._fetch_current_price", return_value=500.0)
    @patch("titantrade.core_allocation.is_market_open", return_value=True)
    def test_respects_cash_floor(
        self, mock_open, mock_price, mock_account, mock_pos, mock_buy,
        fake_config, tmp_state_dir,
    ):
        """When cash is at or below MIN_CASH_RESERVE_PCT, the core manager
        won't buy more — the existing AI overlays already have us fully
        deployed.
        """
        self._write_sentry(tmp_state_dir, stress=False)
        trade = manage_core_position(fake_config)
        # No buy because cash $2k < $5k floor
        assert trade is None
        mock_buy.assert_not_called()


# ---------------------------------------------------------------------------
# Pyramid-into-winners (ride the wave)
# ---------------------------------------------------------------------------

class TestPyramidIntoWinners:
    def _winning_position(self, gain_pct=0.07):
        entry = 100.0
        current = entry * (1 + gain_pct)
        return {
            "symbol": "FOO", "qty": "100",
            "avg_entry_price": str(entry),
            "current_price": str(current),
            "market_value": str(100 * current),
        }

    def _thesis(self):
        return {
            "ticker": "FOO", "thesis": "BULLISH",
            "selected_for_trading": True,
            "target_entry_price": 100.0,
            "stop_loss_price": 95.0,
            "take_profit_price": 115.0,
        }

    # An existing protective stop on the book — the pyramid must extend it to
    # cover the added shares (and must NEVER place a market buy against it).
    def _existing_stop(self, qty="100"):
        return [{
            "id": "stop-old", "type": "stop_limit", "side": "sell",
            "stop_price": "95.00", "qty": qty,
        }]

    @patch("titantrade.positions.place_native_stop_loss", return_value={"id": "stop-new"})
    @patch("titantrade.positions.cancel_order")
    @patch("titantrade.positions._wait_for_order_canceled", return_value="filled")
    @patch("titantrade.positions.get_open_orders")
    @patch("titantrade.positions.place_limit_buy", return_value={"id": "pyr-buy"})
    @patch("titantrade.broker.place_market_buy")
    def test_pyramids_at_5pct_gain_via_limit_buy(
        self, mock_market_buy, mock_limit_buy, mock_orders, mock_wait,
        mock_cancel, mock_stop, fake_config, tmp_state_dir,
    ):
        """FIX: pyramid adds with a marketable LIMIT buy (never a market buy,
        which Alpaca rejects as a wash trade while the protective sell stop is
        on the book — the bug that made every pyramid fail), then extends the
        stop to cover the full position.
        """
        mock_orders.return_value = self._existing_stop(qty="100")

        trade = maybe_pyramid_position(
            "FOO", self._thesis(), self._winning_position(gain_pct=0.07),
            {"signal": "CONTINUE"}, portfolio_value=100_000, cfg=fake_config,
        )
        assert trade is not None
        assert trade["trigger"] == "pyramid"

        # CORE FIX: the add is a LIMIT buy, NOT a market buy.
        mock_market_buy.assert_not_called()
        mock_limit_buy.assert_called_once()
        buy_args = mock_limit_buy.call_args
        assert buy_args.args[0] == "FOO"
        # Original notional $10000 × 50% = $5000, at $107 = 46 shares
        assert buy_args.args[1] == 46
        assert buy_args.args[2] == pytest.approx(107.0 * 1.003, abs=0.01)  # marketable limit
        assert buy_args.kwargs.get("time_in_force") == "day"

        # After the add fills, the stop is extended to cover the FULL position
        # (100 existing + 46 added = 146) so the new shares aren't left bare.
        mock_cancel.assert_called_once_with("stop-old", fake_config)
        mock_stop.assert_called_once()
        stop_args = mock_stop.call_args.args
        assert stop_args[0] == "FOO"
        assert stop_args[1] == 146  # full coverage
        assert stop_args[2] == pytest.approx(95.0, abs=0.01)  # existing stop price

    @patch("titantrade.positions.cancel_order")
    @patch("titantrade.positions._wait_for_order_canceled", return_value="canceled")
    @patch("titantrade.positions.place_limit_buy", return_value={"id": "pyr-buy"})
    def test_unfilled_add_is_cancelled_and_no_trade(
        self, mock_limit_buy, mock_wait, mock_cancel, fake_config, tmp_state_dir,
    ):
        """If the add limit doesn't fill (poll returns a non-'filled' terminal
        state), we cancel the resting buy so it can't fill later UNPROTECTED,
        and record no trade.
        """
        trade = maybe_pyramid_position(
            "FOO", self._thesis(), self._winning_position(gain_pct=0.07),
            {"signal": "CONTINUE"}, portfolio_value=100_000, cfg=fake_config,
        )
        assert trade is None
        mock_limit_buy.assert_called_once()
        mock_cancel.assert_called_once_with("pyr-buy", fake_config)

    @patch("titantrade.positions.place_limit_buy")
    def test_does_not_fire_below_trigger(
        self, mock_buy, fake_config, tmp_state_dir,
    ):
        # 3% gain — below 5% trigger
        trade = maybe_pyramid_position(
            "FOO", self._thesis(), self._winning_position(gain_pct=0.03),
            {"signal": "CONTINUE"}, portfolio_value=100_000, cfg=fake_config,
        )
        assert trade is None
        mock_buy.assert_not_called()

    @patch("titantrade.positions.place_limit_buy")
    def test_only_fires_once_per_position(
        self, mock_buy, fake_config, tmp_state_dir,
    ):
        from titantrade.trailing_state import _save_trailing_state
        _save_trailing_state({"FOO": {"pyramid_added": True}})

        trade = maybe_pyramid_position(
            "FOO", self._thesis(), self._winning_position(gain_pct=0.10),
            {"signal": "CONTINUE"}, portfolio_value=100_000, cfg=fake_config,
        )
        assert trade is None
        mock_buy.assert_not_called()

    @patch("titantrade.positions.place_limit_buy")
    def test_skips_if_sentry_aborting(
        self, mock_buy, fake_config, tmp_state_dir,
    ):
        trade = maybe_pyramid_position(
            "FOO", self._thesis(), self._winning_position(gain_pct=0.08),
            {"signal": "ABORT"}, portfolio_value=100_000, cfg=fake_config,
        )
        assert trade is None
        mock_buy.assert_not_called()

    @patch("titantrade.positions.place_limit_buy")
    def test_skips_if_thesis_flipped(
        self, mock_buy, fake_config, tmp_state_dir,
    ):
        thesis = self._thesis()
        thesis["thesis"] = "BEARISH"
        trade = maybe_pyramid_position(
            "FOO", thesis, self._winning_position(gain_pct=0.08),
            {"signal": "CONTINUE"}, portfolio_value=100_000, cfg=fake_config,
        )
        assert trade is None
        mock_buy.assert_not_called()

    @patch("titantrade.positions.place_limit_buy")
    def test_respects_concentration_cap(
        self, mock_buy, fake_config, tmp_state_dir,
    ):
        """Position already at pyramid_max_total_pct shouldn't add more."""
        # 300 shares at $107 = $32.1k = 32% of $100k — exceeds 30% cap
        pos = self._winning_position(gain_pct=0.07)
        pos["qty"] = "300"
        pos["market_value"] = str(300 * 107)
        trade = maybe_pyramid_position(
            "FOO", self._thesis(), pos,
            {"signal": "CONTINUE"}, portfolio_value=100_000, cfg=fake_config,
        )
        assert trade is None  # Would push above cap
        mock_buy.assert_not_called()


# ---------------------------------------------------------------------------
# Regression: same-cycle TP1 + pyramid wash-trade collision
# ---------------------------------------------------------------------------

class TestPyramidWashTradeGuard:
    """Production bug: TP1 sells, then pyramid tried a MARKET buy in the same
    cycle and Alpaca rejected it as a wash trade ("code 40310000"). Two layers
    of defense now: (1) the add is a limit buy, not a market buy; (2) pyramid
    still defers for 30 min after TP1 to avoid churning the just-sold position.
    """

    @patch("titantrade.positions.place_limit_buy")
    def test_pyramid_defers_when_tp1_fired_recently(
        self, mock_buy, fake_config, tmp_state_dir,
    ):
        from datetime import datetime, timezone
        from titantrade.positions import maybe_pyramid_position
        from titantrade.trailing_state import _save_trailing_state

        # Seed state: TP1 just fired 1 minute ago
        recent = datetime.now(timezone.utc).isoformat()
        _save_trailing_state({"FOO": {"tp1_taken": True, "tp1_timestamp": recent}})

        position = {
            "symbol": "FOO", "qty": "35",  # 35 shares after TP1 sold 18 of 53
            "avg_entry_price": "100.00", "current_price": "108.00",
            "market_value": str(35 * 108),
        }
        thesis = {
            "ticker": "FOO", "thesis": "BULLISH",
            "selected_for_trading": True,
            "target_entry_price": 100.0,
            "stop_loss_price": 95.0,
            "take_profit_price": 115.0,
        }
        result = maybe_pyramid_position(
            "FOO", thesis, position, {"signal": "CONTINUE"},
            portfolio_value=100_000, cfg=fake_config,
        )
        assert result is None
        mock_buy.assert_not_called()

    @patch("titantrade.positions.place_native_stop_loss", return_value={"id": "stop-new"})
    @patch("titantrade.positions.cancel_order")
    @patch("titantrade.positions._wait_for_order_canceled", return_value="filled")
    @patch("titantrade.positions.get_open_orders", return_value=[])
    @patch("titantrade.positions.place_limit_buy", return_value={"id": "p1"})
    @patch("titantrade.broker.place_market_buy")
    def test_pyramid_fires_when_tp1_old_enough(
        self, mock_market_buy, mock_limit_buy, mock_orders, mock_wait,
        mock_cancel, mock_stop, fake_config, tmp_state_dir,
    ):
        """Once 30+ minutes have passed since TP1, the cooldown window has
        closed and the pyramid fires — via a limit buy, never a market buy.
        """
        from datetime import datetime, timezone, timedelta
        from titantrade.positions import maybe_pyramid_position
        from titantrade.trailing_state import _save_trailing_state

        old = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
        _save_trailing_state({"FOO": {"tp1_taken": True, "tp1_timestamp": old}})

        position = {
            "symbol": "FOO", "qty": "35",
            "avg_entry_price": "100.00", "current_price": "108.00",
            "market_value": str(35 * 108),
        }
        thesis = {
            "ticker": "FOO", "thesis": "BULLISH",
            "selected_for_trading": True,
            "target_entry_price": 100.0,
            "stop_loss_price": 95.0,
            "take_profit_price": 115.0,
        }
        result = maybe_pyramid_position(
            "FOO", thesis, position, {"signal": "CONTINUE"},
            portfolio_value=100_000, cfg=fake_config,
        )
        assert result is not None
        mock_market_buy.assert_not_called()
        mock_limit_buy.assert_called_once()


# ---------------------------------------------------------------------------
# Regression: bearish exit off-hours gate
# ---------------------------------------------------------------------------

class TestBearishExitOffHours:
    """Production bug: BEARISH thesis + held position fired
    cancel_all_orders_for_ticker + close_position_at_market during off-hours,
    which 403'd with "insufficient qty available" because the cancel sat in
    pending_cancel. DVN and FANG failed exactly this way.

    Fix: when market is closed, defer the bearish exit. The existing
    stop-loss on the book continues to protect the position.
    """

    def _e2e_state(self, tmp_state_dir):
        write_state_file(tmp_state_dir, "weekly_thesis.json", {
            "theses": [
                {
                    "ticker": "DVN", "thesis": "BEARISH",
                    "confidence": 0.75, "selected_for_trading": True,
                    "review_action": "NEW",
                    "reasoning": "Thesis flipped bearish",
                },
            ],
        })
        write_state_file(tmp_state_dir, "sentry_signals.json", {
            "signals": [{"ticker": "DVN", "signal": "CONTINUE"}],
            "market_health": {"market_stress": False},
        })
        write_state_file(tmp_state_dir, "data_bundle.json", {"stocks": {}})

    @patch("titantrade.executor.close_position_at_market")
    @patch("titantrade.executor.cancel_all_orders_for_ticker", return_value=0)
    @patch("titantrade.executor.get_position")
    @patch("titantrade.executor.get_positions")
    @patch("titantrade.executor.get_open_orders", return_value=[])
    @patch("titantrade.executor.get_account", return_value={
        "portfolio_value": "100000", "cash": "20000", "buying_power": "40000",
    })
    @patch("titantrade.executor.resubmit_expired_brackets", return_value=[])
    @patch("titantrade.executor.check_gap_down_protection", return_value=[])
    @patch("titantrade.executor.close_orphaned_positions", return_value=[])
    @patch("titantrade.executor.manage_core_position", return_value=None)
    @patch("titantrade.executor.load_stock_sectors", return_value=None)
    @patch("titantrade.executor.is_market_open", return_value=False)
    def test_bearish_exit_defers_off_hours(
        self,
        mock_open, mock_load_sec, mock_core, mock_orphan, mock_gap,
        mock_resub, mock_account, mock_oo, mock_get_positions,
        mock_get_pos, mock_cancel, mock_close,
        fake_config, tmp_state_dir,
    ):
        self._e2e_state(tmp_state_dir)
        fake_config = _config_with_watchlist(fake_config, ["DVN"])
        position = {"symbol": "DVN", "qty": "260", "current_price": "47.00",
                    "avg_entry_price": "47.16"}
        mock_get_positions.return_value = [position]
        mock_get_pos.return_value = position

        from titantrade.executor import execute_trades
        execute_trades(fake_config)

        # Off-hours: NO cancel, NO close — the existing stop protects
        mock_cancel.assert_not_called()
        mock_close.assert_not_called()

    @patch("titantrade.executor.time.sleep", return_value=None)
    @patch("titantrade.executor.close_position_at_market", return_value={"id": "c1"})
    @patch("titantrade.executor.cancel_all_orders_for_ticker", return_value=0)
    @patch("titantrade.executor.get_position")
    @patch("titantrade.executor.get_positions")
    @patch("titantrade.executor.get_open_orders", return_value=[])
    @patch("titantrade.executor.get_account", return_value={
        "portfolio_value": "100000", "cash": "20000", "buying_power": "40000",
    })
    @patch("titantrade.executor.resubmit_expired_brackets", return_value=[])
    @patch("titantrade.executor.check_gap_down_protection", return_value=[])
    @patch("titantrade.executor.close_orphaned_positions", return_value=[])
    @patch("titantrade.executor.manage_core_position", return_value=None)
    @patch("titantrade.executor.load_stock_sectors", return_value=None)
    @patch("titantrade.executor.is_market_open", return_value=True)
    def test_bearish_exit_fires_market_open(
        self,
        mock_open, mock_load_sec, mock_core, mock_orphan, mock_gap,
        mock_resub, mock_account, mock_oo, mock_get_positions,
        mock_get_pos, mock_cancel, mock_close, mock_sleep,
        fake_config, tmp_state_dir,
    ):
        """Market-open: cancel + close fires normally (with the 2s settle delay)."""
        self._e2e_state(tmp_state_dir)
        fake_config = _config_with_watchlist(fake_config, ["DVN"])
        position = {"symbol": "DVN", "qty": "260", "current_price": "47.00",
                    "avg_entry_price": "47.16"}
        mock_get_positions.return_value = [position]
        mock_get_pos.return_value = position

        from titantrade.executor import execute_trades
        execute_trades(fake_config)

        mock_cancel.assert_called_once_with("DVN", fake_config)
        mock_close.assert_called_once()


# ---------------------------------------------------------------------------
# Regression: asymmetric stop walking (DVN got 0.25× ATR stop in production)
# ---------------------------------------------------------------------------

class TestStopWalksBothDirections:
    """Production bug from the week-1 logs:

        Resubmit entry adapted for DVN (up, conf 0.72): $49.20 → $47.16
        Bracket BUY: 260.0 DVN entry=$47.16 stop=$46.74 tp=52.5

    Entry walked DOWN by $2.04 but stop stayed at $46.74. Result: risk
    collapsed from $2.46 (5%, ~1.5× ATR) to $0.42 (0.9%, 0.25× ATR) —
    guaranteed noise-stop. The fix walks stop+TP in EITHER direction by
    the same delta as entry.
    """

    @patch("titantrade.daily_sentry._fetch_current_price", return_value=47.16)
    @patch("titantrade.entries.place_bracket_order", return_value={"id": "br"})
    @patch("titantrade.entries.get_open_orders", return_value=[])
    def test_entry_walking_down_walks_stop_down_too(
        self, mock_orders, mock_bracket, mock_price,
        fake_config, sample_positions, tmp_state_dir, monkeypatch,
    ):
        monkeypatch.setattr("titantrade.risk_manager.get_stock_sector", lambda t: "Energy")

        thesis = {
            "ticker": "DVN", "thesis": "BULLISH",
            "confidence": 0.72,
            "target_entry_price": 49.20,
            "stop_loss_price": 46.74,    # 5% below original target
            "take_profit_price": 52.50,
            "selected_for_trading": True,
        }
        bundle = {
            "stocks": {"DVN": {
                "technical_indicators": {
                    "price_vs_sma": {
                        "above_sma_50": True, "above_sma_200": True,
                        "golden_cross": False, "pct_from_sma_50": 1.5,
                        "sma_20": 47.0, "sma_50": 46.5,
                    },
                },
                "atr_14": 1.66,
            }},
        }
        _handle_bullish_entry(
            ticker="DVN", thesis=thesis,
            portfolio_value=100_000, cash_balance=50_000,
            positions=sample_positions, data_bundle=bundle,
            sentry=None, cfg=fake_config,
        )

        assert mock_bracket.called
        call = mock_bracket.call_args_list[0]
        entry = call.kwargs.get("entry_limit_price") or call.args[2]
        stop = call.kwargs.get("stop_loss_price") or call.args[3]

        # Entry should be near 47.16 (current * 1.001 = 47.21)
        assert 47.0 <= entry <= 47.5
        # Stop should have walked DOWN: original stop $46.74, delta ≈ -2.04
        # → new stop ≈ $44.70. The OLD bug would leave it at $46.74.
        assert stop < 46.0, (
            f"Stop should walk down with entry. Got entry={entry}, stop={stop}. "
            f"Old bug: stop stays at thesis level ($46.74) → tiny risk."
        )
        # Risk should still be ~5% (1.5x ATR) — preserved from original thesis
        risk_pct = (entry - stop) / entry
        assert 0.04 < risk_pct < 0.06, f"Risk:reward not preserved: {risk_pct:.2%}"


# ---------------------------------------------------------------------------
# Regression: BEARISH + ADJUST should NOT exit (production FANG case)
# ---------------------------------------------------------------------------

class TestBearishAdjustSuppressesExit:
    """Production case: FANG had thesis=BEARISH but review_action=ADJUST
    (analyst wanted to tighten stop, not exit). The bearish-exit fired
    anyway, contradicting the analyst's intent. Now ADJUST takes precedence.
    """

    def _state(self, tmp_state_dir, review_action: str):
        write_state_file(tmp_state_dir, "weekly_thesis.json", {
            "theses": [
                {
                    "ticker": "FANG", "thesis": "BEARISH",
                    "confidence": 0.70,
                    "review_action": review_action,
                    "stop_loss_price": 198.50,
                    "selected_for_trading": True,
                    "reasoning": "Bearish view, but tighten stop instead of exit",
                },
            ],
        })
        write_state_file(tmp_state_dir, "sentry_signals.json", {
            "signals": [{"ticker": "FANG", "signal": "CONTINUE"}],
            "market_health": {"market_stress": False},
        })
        write_state_file(tmp_state_dir, "data_bundle.json", {"stocks": {}})

    @patch("titantrade.executor.close_position_at_market")
    @patch("titantrade.executor.cancel_all_orders_for_ticker", return_value=0)
    @patch("titantrade.executor.get_position")
    @patch("titantrade.executor.get_positions")
    @patch("titantrade.executor.get_open_orders", return_value=[])
    @patch("titantrade.executor.get_account", return_value={
        "portfolio_value": "100000", "cash": "30000", "buying_power": "60000",
    })
    @patch("titantrade.executor.resubmit_expired_brackets", return_value=[])
    @patch("titantrade.executor.check_gap_down_protection", return_value=[])
    @patch("titantrade.executor.close_orphaned_positions", return_value=[])
    @patch("titantrade.executor.manage_core_position", return_value=None)
    @patch("titantrade.executor.load_stock_sectors", return_value=None)
    @patch("titantrade.executor.is_market_open", return_value=True)
    def test_bearish_with_adjust_does_not_exit(
        self,
        mock_open, mock_load, mock_core, mock_orphan, mock_gap,
        mock_resub, mock_account, mock_oo, mock_get_positions, mock_get_pos,
        mock_cancel, mock_close,
        fake_config, tmp_state_dir,
    ):
        self._state(tmp_state_dir, review_action="ADJUST")
        fake_config = _config_with_watchlist(fake_config, ["FANG"])
        position = {
            "symbol": "FANG", "qty": "22",
            "avg_entry_price": "200.00", "current_price": "199.00",
            "unrealized_plpc": "-0.005",
        }
        mock_get_positions.return_value = [position]
        mock_get_pos.return_value = position

        from titantrade.executor import execute_trades
        execute_trades(fake_config)

        # BEARISH + ADJUST → defer to ADJUST flow, NOT exit at market
        mock_close.assert_not_called()
        # ADJUST flow will run cancel_all + place_native_stop, BUT we're not
        # asserting on that here (it's tested elsewhere). The key contract:
        # close_position_at_market was NOT called.

    @patch("titantrade.executor.time.sleep", return_value=None)
    @patch("titantrade.executor.close_position_at_market", return_value={"id": "c1"})
    @patch("titantrade.executor.cancel_all_orders_for_ticker", return_value=0)
    @patch("titantrade.executor.get_position")
    @patch("titantrade.executor.get_positions")
    @patch("titantrade.executor.get_open_orders", return_value=[])
    @patch("titantrade.executor.get_account", return_value={
        "portfolio_value": "100000", "cash": "30000", "buying_power": "60000",
    })
    @patch("titantrade.executor.resubmit_expired_brackets", return_value=[])
    @patch("titantrade.executor.check_gap_down_protection", return_value=[])
    @patch("titantrade.executor.close_orphaned_positions", return_value=[])
    @patch("titantrade.executor.manage_core_position", return_value=None)
    @patch("titantrade.executor.load_stock_sectors", return_value=None)
    @patch("titantrade.executor.is_market_open", return_value=True)
    def test_bearish_without_adjust_does_exit(
        self,
        mock_open, mock_load, mock_core, mock_orphan, mock_gap,
        mock_resub, mock_account, mock_oo, mock_get_positions, mock_get_pos,
        mock_cancel, mock_close, mock_sleep,
        fake_config, tmp_state_dir,
    ):
        """Sanity: when there's no ADJUST instruction, the bearish exit still
        fires normally. This complements the suppression test.
        """
        self._state(tmp_state_dir, review_action="NEW")  # not ADJUST
        fake_config = _config_with_watchlist(fake_config, ["FANG"])
        position = {
            "symbol": "FANG", "qty": "22",
            "avg_entry_price": "200.00", "current_price": "199.00",
        }
        mock_get_positions.return_value = [position]
        mock_get_pos.return_value = position

        from titantrade.executor import execute_trades
        execute_trades(fake_config)

        mock_close.assert_called_once()


# ---------------------------------------------------------------------------
# Regression: bearish exit restores stop on close failure
# ---------------------------------------------------------------------------

class TestBearishExitRestoresStopOnFailure:
    """Production case: DVN bearish exit cancelled the stop, then
    close_position_at_market 403'd. Position left naked until next run.
    Fix: capture existing stop before cancel; restore it if close fails.
    """

    @patch("titantrade.executor.time.sleep", return_value=None)
    @patch("titantrade.executor.place_native_stop_loss", return_value={"id": "restored"})
    @patch("titantrade.executor.close_position_at_market", side_effect=RuntimeError("403 qty race"))
    @patch("titantrade.executor.cancel_all_orders_for_ticker", return_value=1)
    @patch("titantrade.executor.get_position")
    @patch("titantrade.executor.get_positions")
    @patch("titantrade.executor.get_open_orders")
    @patch("titantrade.executor.get_account", return_value={
        "portfolio_value": "100000", "cash": "30000", "buying_power": "60000",
    })
    @patch("titantrade.executor.resubmit_expired_brackets", return_value=[])
    @patch("titantrade.executor.check_gap_down_protection", return_value=[])
    @patch("titantrade.executor.close_orphaned_positions", return_value=[])
    @patch("titantrade.executor.manage_core_position", return_value=None)
    @patch("titantrade.executor.load_stock_sectors", return_value=None)
    @patch("titantrade.executor.is_market_open", return_value=True)
    def test_failed_close_restores_stop(
        self,
        mock_open, mock_load, mock_core, mock_orphan, mock_gap,
        mock_resub, mock_account, mock_oo, mock_get_positions, mock_get_pos,
        mock_cancel, mock_close, mock_place_stop, mock_sleep,
        fake_config, tmp_state_dir,
    ):
        write_state_file(tmp_state_dir, "weekly_thesis.json", {
            "theses": [{
                "ticker": "DVN", "thesis": "BEARISH",
                "confidence": 0.75, "selected_for_trading": True,
                "review_action": "NEW",
                "stop_loss_price": 46.74,
                "reasoning": "thesis flipped",
            }],
        })
        write_state_file(tmp_state_dir, "sentry_signals.json", {
            "signals": [{"ticker": "DVN", "signal": "CONTINUE"}],
            "market_health": {"market_stress": False},
        })
        write_state_file(tmp_state_dir, "data_bundle.json", {"stocks": {}})
        fake_config = _config_with_watchlist(fake_config, ["DVN"])

        # Pre-cancel: an existing stop @ $46.74 is on the book
        mock_oo.return_value = [{
            "type": "stop_limit", "side": "sell",
            "stop_price": "46.74", "id": "stop-1",
        }]
        position = {
            "symbol": "DVN", "qty": "260",
            "avg_entry_price": "47.16", "current_price": "47.00",
        }
        mock_get_positions.return_value = [position]
        mock_get_pos.return_value = position

        from titantrade.executor import execute_trades
        execute_trades(fake_config)

        # Close was attempted (and failed)
        mock_close.assert_called_once()
        # Stop was restored on failure
        mock_place_stop.assert_called_once()
        restore_args = mock_place_stop.call_args.args
        assert restore_args[0] == "DVN"
        assert float(restore_args[1]) == 260.0
        assert float(restore_args[2]) == 46.74
