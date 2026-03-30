"""Tests for the Discord notification module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from titantrade.notifier import (
    COLOR_FAILURE,
    COLOR_SUCCESS,
    COLOR_SUMMARY,
    notify_job_completed,
    notify_job_failed,
    send_daily_summary,
    send_discord,
)


@pytest.fixture(autouse=True)
def _mock_env(monkeypatch: pytest.MonkeyPatch):
    """Set a fake webhook URL for all tests by default."""
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test/fake")


class TestSendDiscord:
    def test_sends_embed(self):
        with patch("titantrade.notifier.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            send_discord("Test Title", "Test body", COLOR_SUCCESS)

            mock_post.assert_called_once()
            payload = mock_post.call_args.kwargs["json"]
            embed = payload["embeds"][0]
            assert embed["title"] == "Test Title"
            assert embed["description"] == "Test body"
            assert embed["color"] == COLOR_SUCCESS

    def test_sends_with_fields(self):
        with patch("titantrade.notifier.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            fields = [{"name": "Key", "value": "Val", "inline": True}]
            send_discord("Title", fields=fields)

            payload = mock_post.call_args.kwargs["json"]
            assert payload["embeds"][0]["fields"] == fields

    def test_noop_without_webhook_url(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
        with patch("titantrade.notifier.httpx.post") as mock_post:
            send_discord("Should not send")
            mock_post.assert_not_called()

    def test_empty_webhook_url_is_noop(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "  ")
        with patch("titantrade.notifier.httpx.post") as mock_post:
            send_discord("Should not send")
            mock_post.assert_not_called()

    def test_http_error_logged_not_raised(self):
        with patch("titantrade.notifier.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=500, text="Internal Server Error")
            # Should not raise
            send_discord("Test")

    def test_network_error_logged_not_raised(self):
        with patch("titantrade.notifier.httpx.post") as mock_post:
            mock_post.side_effect = ConnectionError("no connection")
            # Should not raise
            send_discord("Test")


class TestJobNotifications:
    def test_completed_notification(self):
        with patch("titantrade.notifier.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            notify_job_completed("Morning Sentry", "sentry + 2 trades", 45.3)

            payload = mock_post.call_args.kwargs["json"]
            embed = payload["embeds"][0]
            assert "Morning Sentry" in embed["title"]
            assert embed["color"] == COLOR_SUCCESS
            field_names = [f["name"] for f in embed["fields"]]
            assert "Result" in field_names
            assert "Duration" in field_names

    def test_completed_without_result(self):
        with patch("titantrade.notifier.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            notify_job_completed("Price Check", None, 3.0)

            payload = mock_post.call_args.kwargs["json"]
            field_names = [f["name"] for f in payload["embeds"][0]["fields"]]
            assert "Result" not in field_names
            assert "Duration" in field_names

    def test_failed_notification(self):
        with patch("titantrade.notifier.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            notify_job_failed("Gap Check", "FMP API returned 403", 12.0)

            payload = mock_post.call_args.kwargs["json"]
            embed = payload["embeds"][0]
            assert "failed" in embed["title"].lower()
            assert embed["color"] == COLOR_FAILURE
            error_field = next(f for f in embed["fields"] if f["name"] == "Error")
            assert "403" in error_field["value"]

    def test_long_error_truncated(self):
        with patch("titantrade.notifier.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            long_error = "x" * 2000
            notify_job_failed("Test", long_error, 1.0)

            payload = mock_post.call_args.kwargs["json"]
            error_field = next(f for f in payload["embeds"][0]["fields"] if f["name"] == "Error")
            # 1000 chars + markdown code fences
            assert len(error_field["value"]) < 1020


class TestDailySummary:
    @pytest.fixture
    def state_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        monkeypatch.setattr("titantrade.notifier.STATE_DIR", tmp_path)
        return tmp_path

    def test_sends_summary_with_portfolio(self, state_dir: Path):
        (state_dir / "portfolio.json").write_text(json.dumps({
            "portfolio_value": 52340.50,
            "cash": 10000.00,
            "positions": [
                {"symbol": "CRWD", "unrealized_plpc": 0.032},
                {"symbol": "LLY", "unrealized_plpc": -0.008},
            ],
        }))

        with patch("titantrade.notifier.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            result = send_daily_summary()

            assert result == "daily summary sent"
            mock_post.assert_called_once()
            payload = mock_post.call_args.kwargs["json"]
            embed = payload["embeds"][0]
            assert embed["color"] == COLOR_SUMMARY
            field_names = [f["name"] for f in embed["fields"]]
            assert "Portfolio Value" in field_names
            assert any("Positions" in n for n in field_names)

    def test_sends_summary_with_sentry_signals(self, state_dir: Path):
        (state_dir / "portfolio.json").write_text(json.dumps({
            "portfolio_value": 50000,
            "cash": 10000,
            "positions": [],
        }))
        (state_dir / "sentry_signals.json").write_text(json.dumps({
            "signals": [
                {"ticker": "CRWD", "signal": "CONTINUE"},
                {"ticker": "LLY", "signal": "CONTINUE"},
                {"ticker": "DVN", "signal": "ABORT"},
            ],
        }))

        with patch("titantrade.notifier.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            send_daily_summary()

            payload = mock_post.call_args.kwargs["json"]
            sentry_field = next(
                f for f in payload["embeds"][0]["fields"]
                if f["name"] == "Sentry Signals"
            )
            assert "CONTINUE x2" in sentry_field["value"]
            assert "ABORT x1" in sentry_field["value"]
            assert "DVN" in sentry_field["value"]

    def test_handles_missing_state_files(self, state_dir: Path):
        """Summary still sends even with no state files (just shows mode)."""
        with patch("titantrade.notifier.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            result = send_daily_summary()

            assert result == "daily summary sent"

    def test_trailing_stops_included(self, state_dir: Path):
        (state_dir / "portfolio.json").write_text(json.dumps({
            "portfolio_value": 50000,
            "cash": 10000,
            "positions": [],
        }))
        (state_dir / "trailing_stops.json").write_text(json.dumps({
            "CRWD": {"ticker": "CRWD", "active": True, "trail_price": 182.50},
            "LLY": {"ticker": "LLY", "active": False, "trail_price": 0},
        }))

        with patch("titantrade.notifier.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            send_daily_summary()

            payload = mock_post.call_args.kwargs["json"]
            field_names = [f["name"] for f in payload["embeds"][0]["fields"]]
            trailing_field = next(f for f in payload["embeds"][0]["fields"] if "Trailing" in f["name"])
            assert "CRWD" in trailing_field["value"]
            assert "$182.50" in trailing_field["value"]

    def test_notification_failure_does_not_crash(self, state_dir: Path):
        (state_dir / "portfolio.json").write_text(json.dumps({
            "portfolio_value": 50000,
            "cash": 10000,
            "positions": [],
        }))

        with patch("titantrade.notifier.httpx.post") as mock_post:
            mock_post.side_effect = ConnectionError("no internet")
            # Should not raise — send_discord swallows the exception
            result = send_daily_summary()
            assert result == "daily summary sent"
