"""Alpaca client: stop placement races, bracket guards, market hours, cancel polling.
All HTTP mocked at ``fetch_with_retry``."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from titantrade.broker import (
    _wait_for_order_canceled, is_market_open, place_bracket_order, place_native_stop_loss,
)
from titantrade.retry import HTTPError


def _resp(data):
    m = MagicMock()
    m.json.return_value = data
    return m


def _qty_race_error(blocking_id: str, available: str = "0") -> HTTPError:
    return HTTPError(
        status_code=403,
        body=json.dumps({
            "code": 40310000, "available": available, "existing_qty": "121",
            "held_for_orders": "121", "related_orders": [blocking_id],
            "message": f"insufficient qty available for order (requested: 121, available: {available})",
            "symbol": "FCX",
        }),
        url="https://paper-api.alpaca.markets/v2/orders", method="POST",
    )


class TestPlaceNativeStopLoss:
    @patch("titantrade.broker.time.sleep")
    @patch("titantrade.broker.get_order")
    @patch("titantrade.broker.fetch_with_retry")
    def test_retries_after_the_blocking_order_settles(self, mock_fetch, mock_get_order, mock_sleep, fake_config):
        mock_fetch.side_effect = [_qty_race_error("blocking-1"), _resp({"id": "order-abc", "status": "accepted"})]
        mock_get_order.side_effect = [{"status": "pending_cancel"}, {"status": "pending_cancel"}, {"status": "canceled"}]
        result = place_native_stop_loss("FCX", 121, 64.50, fake_config)
        assert result["id"] == "order-abc" and mock_fetch.call_count == 2
        assert all(c.args[0] == "blocking-1" for c in mock_get_order.call_args_list)

    @patch("titantrade.broker._wait_for_order_canceled", return_value=None)
    @patch("titantrade.broker.fetch_with_retry")
    def test_raises_when_the_cancel_never_settles(self, mock_fetch, mock_wait, fake_config):
        mock_fetch.side_effect = [_qty_race_error("stuck")]
        with pytest.raises(HTTPError) as exc_info:
            place_native_stop_loss("FCX", 121, 64.50, fake_config)
        assert exc_info.value.error_code == 40310000
        mock_wait.assert_called_once_with("stuck", fake_config)

    @patch("titantrade.broker.fetch_with_retry")
    def test_clamps_to_available_qty_when_no_blocking_order(self, mock_fetch, fake_config):
        race = HTTPError(
            status_code=403,
            body='{"code":40310000,"available":"103","existing_qty":"103","held_for_orders":"0","message":"insufficient qty","symbol":"FCX"}',
            url="u", method="POST",
        )
        mock_fetch.side_effect = [race, _resp({"id": "clamped", "status": "accepted"})]
        assert place_native_stop_loss("FCX", 121, 64.50, fake_config)["id"] == "clamped"
        assert mock_fetch.call_args_list[1].kwargs["json_body"]["qty"] == "103.0"

    @patch("titantrade.broker.fetch_with_retry")
    def test_raises_without_blocking_order_or_available(self, mock_fetch, fake_config):
        mock_fetch.side_effect = [HTTPError(status_code=403, body='{"code":40310000,"message":"insufficient qty","symbol":"FCX"}', url="u", method="POST")]
        with pytest.raises(HTTPError):
            place_native_stop_loss("FCX", 121, 64.50, fake_config)

    @patch("titantrade.broker.fetch_with_retry")
    def test_falls_back_to_plain_stop_on_other_4xx(self, mock_fetch, fake_config):
        mock_fetch.side_effect = [HTTPError(status_code=422, body='{"code":42210000,"message":"no"}', url="u", method="POST"), _resp({"id": "xyz"})]
        assert place_native_stop_loss("FOO", 10, 50.0, fake_config)["id"] == "xyz"
        assert [c.kwargs["json_body"]["type"] for c in mock_fetch.call_args_list] == ["stop_limit", "stop"]

    @patch("titantrade.broker.fetch_with_retry")
    def test_floors_fractional_qty_and_skips_dust(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp({"id": "stop-1"})
        place_native_stop_loss("GE", 5.7, 344.0, fake_config)
        body = mock_fetch.call_args.kwargs["json_body"]
        assert body["qty"] == "5.0" and body["time_in_force"] == "gtc"
        mock_fetch.reset_mock()
        assert place_native_stop_loss("JPM", 0.13, 314.5, fake_config) == {}
        mock_fetch.assert_not_called()


class TestBracketGuard:
    @patch("titantrade.broker.fetch_with_retry")
    def test_floors_fractional_qty(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp({"id": "br-1"})
        place_bracket_order("AAPL", 5.9, 100.0, 95.0, 110.0, fake_config)
        assert mock_fetch.call_args.kwargs["json_body"]["qty"] == "5.0"

    def test_raises_below_one_share(self, fake_config):
        with pytest.raises(ValueError, match="whole share"):
            place_bracket_order("URI", 0.19, 990.0, 922.0, 1046.0, fake_config)


class TestMarketHours:
    @patch("titantrade.broker.fetch_with_retry")
    def test_open_and_closed(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp({"is_open": True})
        assert is_market_open(fake_config) is True
        mock_fetch.return_value = _resp({"is_open": False})
        assert is_market_open(fake_config) is False

    @patch("titantrade.broker.fetch_with_retry", side_effect=RuntimeError("clock unreachable"))
    def test_assumes_open_on_error(self, mock_fetch, fake_config):
        assert is_market_open(fake_config) is True


class TestWaitForOrderCanceled:
    @patch("titantrade.broker.time.sleep")
    @patch("titantrade.broker.get_order")
    def test_polls_until_terminal(self, mock_get, mock_sleep, fake_config):
        mock_get.side_effect = [{"status": "pending_cancel"}, {"status": "canceled"}]
        assert _wait_for_order_canceled("oid", fake_config) == "canceled"
        mock_get.return_value = {"status": "filled"}
        mock_get.side_effect = None
        assert _wait_for_order_canceled("oid", fake_config) == "filled"

    @patch("titantrade.broker.time.sleep")
    @patch("titantrade.broker.get_order", return_value=None)
    def test_missing_order_counts_as_canceled(self, mock_get, mock_sleep, fake_config):
        assert _wait_for_order_canceled("oid", fake_config) == "canceled"

    @patch("titantrade.broker.time.time")
    @patch("titantrade.broker.time.sleep")
    @patch("titantrade.broker.get_order", return_value={"status": "pending_cancel"})
    def test_times_out(self, mock_get, mock_sleep, mock_time, fake_config):
        mock_time.side_effect = [0.0, 0.0, 200.0, 200.0, 200.0, 200.0]
        assert _wait_for_order_canceled("oid", fake_config) is None
