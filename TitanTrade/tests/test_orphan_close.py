"""Tests for orphaned position closing.

All broker calls mocked. Zero real orders.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest

from titantrade.executor import close_orphaned_positions
from tests.conftest import write_state_file


@pytest.fixture(autouse=True)
def _mock_sector(monkeypatch):
    monkeypatch.setattr("titantrade.risk_manager.get_stock_sector", lambda t: "Technology")


class TestReviewActionClose:
    @patch("titantrade.executor._cleanup_trailing_state")
    @patch("titantrade.executor.close_position_at_market")
    @patch("titantrade.executor.cancel_all_orders_for_ticker", return_value=0)
    @patch("titantrade.executor.get_positions")
    def test_closes_position_on_close_review(
        self, mock_pos, mock_cancel, mock_close, mock_cleanup,
        fake_config, tmp_state_dir,
    ):
        write_state_file(tmp_state_dir, "weekly_thesis.json", {
            "theses": [{"ticker": "AAPL", "thesis": "BEARISH", "review_action": "CLOSE",
                        "reasoning": "Thesis invalidated"}],
        })
        mock_pos.return_value = [
            {"symbol": "AAPL", "qty": "50", "current_price": "185.00"},
        ]
        result = close_orphaned_positions(fake_config)
        assert len(result) == 1
        assert result[0]["trigger"] == "thesis_expired"
        assert result[0]["ticker"] == "AAPL"
        mock_close.assert_called_once()

    @patch("titantrade.executor.close_position_at_market")
    @patch("titantrade.executor.cancel_all_orders_for_ticker")
    @patch("titantrade.executor.get_positions")
    def test_no_close_on_continue_review(
        self, mock_pos, mock_cancel, mock_close,
        fake_config, tmp_state_dir,
    ):
        write_state_file(tmp_state_dir, "weekly_thesis.json", {
            "theses": [{"ticker": "AAPL", "thesis": "BULLISH", "review_action": "CONTINUE"}],
        })
        mock_pos.return_value = [
            {"symbol": "AAPL", "qty": "50", "current_price": "185.00"},
        ]
        result = close_orphaned_positions(fake_config)
        assert len(result) == 0
        mock_close.assert_not_called()


class TestMissingThesisEntry:
    @patch("titantrade.executor._cleanup_trailing_state")
    @patch("titantrade.executor.close_position_at_market")
    @patch("titantrade.executor.cancel_all_orders_for_ticker", return_value=0)
    @patch("titantrade.executor.get_positions")
    def test_closes_position_not_in_thesis(
        self, mock_pos, mock_cancel, mock_close, mock_cleanup,
        fake_config, tmp_state_dir,
    ):
        """Position held for TSLA but thesis only has AAPL."""
        future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        write_state_file(tmp_state_dir, "weekly_thesis.json", {
            "theses": [{"ticker": "AAPL", "thesis": "BULLISH"}],
            "expires_at": future,
        })
        mock_pos.return_value = [
            {"symbol": "TSLA", "qty": "30", "current_price": "250.00"},
        ]
        result = close_orphaned_positions(fake_config)
        assert len(result) == 1
        assert result[0]["ticker"] == "TSLA"
        mock_close.assert_called_once()

    @patch("titantrade.executor.close_position_at_market")
    @patch("titantrade.executor.cancel_all_orders_for_ticker")
    @patch("titantrade.executor.get_positions")
    def test_keeps_position_in_thesis(
        self, mock_pos, mock_cancel, mock_close,
        fake_config, tmp_state_dir,
    ):
        future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        write_state_file(tmp_state_dir, "weekly_thesis.json", {
            "theses": [{"ticker": "AAPL", "thesis": "BULLISH"}],
            "expires_at": future,
        })
        mock_pos.return_value = [
            {"symbol": "AAPL", "qty": "50", "current_price": "185.00"},
        ]
        result = close_orphaned_positions(fake_config)
        assert len(result) == 0


class TestEdgeCases:
    @patch("titantrade.executor.get_positions", return_value=[])
    def test_no_positions_returns_empty(self, mock_pos, fake_config, tmp_state_dir):
        write_state_file(tmp_state_dir, "weekly_thesis.json", {"theses": []})
        result = close_orphaned_positions(fake_config)
        assert result == []

    @patch("titantrade.executor.get_positions", return_value=[])
    def test_missing_thesis_file_returns_empty(self, mock_pos, fake_config, tmp_state_dir):
        # No weekly_thesis.json at all
        result = close_orphaned_positions(fake_config)
        assert result == []

    @patch("titantrade.executor.get_positions")
    def test_skips_zero_qty_positions(self, mock_pos, fake_config, tmp_state_dir):
        future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        write_state_file(tmp_state_dir, "weekly_thesis.json", {
            "theses": [],
            "expires_at": future,
        })
        mock_pos.return_value = [
            {"symbol": "AAPL", "qty": "0", "current_price": "185.00"},
        ]
        result = close_orphaned_positions(fake_config)
        assert len(result) == 0
