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
    # ADR 058 retry backoff must not slow the suite down.
    monkeypatch.setattr("titantrade.notifier.time.sleep", lambda _s: None)


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

    def test_sends_summary_with_plan(self, state_dir: Path):
        (state_dir / "portfolio.json").write_text(json.dumps({"portfolio_value": 50000, "cash": 10000, "positions": []}))
        (state_dir / "plan.json").write_text(json.dumps({
            "insurance": {"risk_off": False, "spy_above_sma": True, "sector_breadth": 0.45},
            "held": ["DASH", "JPM"], "free_slots": 1,
            "candidates": [{"ticker": "URI", "dip_pct": 0.09, "chosen": True}],
        }))
        with patch("titantrade.notifier.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            send_daily_summary()
            payload = mock_post.call_args.kwargs["json"]
            plan_field = next(f for f in payload["embeds"][0]["fields"] if f["name"] == "Plan")
            assert "insurance on" in plan_field["value"]
            assert "DASH, JPM" in plan_field["value"] and "URI" in plan_field["value"]

    def test_handles_missing_state_files(self, state_dir: Path):
        """Summary still sends even with no state files (just shows mode)."""
        with patch("titantrade.notifier.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            result = send_daily_summary()

            assert result == "daily summary sent"

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


class TestSendDiscordRetry:
    """ADR 058: a transient 503 (production 2026-09-17) lost a job notification
    because the webhook was a single POST. Transport errors, 429 and 5xx are
    retried twice with backoff; other 4xx are ours and are not retried."""

    def test_503_then_200_posts_twice(self):
        with patch("titantrade.notifier.httpx.post") as mock_post:
            mock_post.side_effect = [
                MagicMock(status_code=503, text="upstream connect error"),
                MagicMock(status_code=204, text=""),
            ]
            send_discord("Test")
            assert mock_post.call_count == 2

    def test_transport_error_then_200_posts_twice(self):
        with patch("titantrade.notifier.httpx.post") as mock_post:
            mock_post.side_effect = [ConnectionError("reset"), MagicMock(status_code=204, text="")]
            send_discord("Test")
            assert mock_post.call_count == 2

    def test_429_is_retried(self):
        with patch("titantrade.notifier.httpx.post") as mock_post:
            mock_post.side_effect = [
                MagicMock(status_code=429, text="rate limited"),
                MagicMock(status_code=204, text=""),
            ]
            send_discord("Test")
            assert mock_post.call_count == 2

    def test_other_4xx_is_not_retried(self):
        with patch("titantrade.notifier.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=400, text="bad embed")
            send_discord("Test")
            mock_post.assert_called_once()

    def test_gives_up_after_three_attempts_without_raising(self):
        with patch("titantrade.notifier.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=503, text="still down")
            send_discord("Test")
            assert mock_post.call_count == 3

    def test_success_first_time_posts_once(self):
        with patch("titantrade.notifier.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=204, text="")
            send_discord("Test")
            mock_post.assert_called_once()
