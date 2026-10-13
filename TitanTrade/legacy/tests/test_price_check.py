"""Tests for lightweight intraday price checks.

All broker and FMP API calls are mocked. Zero tokens, zero orders.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from titantrade.price_check import run_price_check
from tests.conftest import write_state_file


@pytest.fixture(autouse=True)
def _redirect_state(tmp_state_dir, monkeypatch):
    monkeypatch.setattr("titantrade.price_check.STATE_DIR", tmp_state_dir)


@pytest.fixture
def thesis_doc():
    return {
        "theses": [
            {
                "ticker": "AAPL",
                "thesis": "BULLISH",
                "confidence": 0.80,
                "target_entry_price": 185.50,
            },
        ],
        "expires_at": "2099-01-01T00:00:00+00:00",
    }


class TestPriceCheckNoPositions:
    @patch("titantrade.price_check.get_positions", return_value=[])
    def test_no_positions_no_aborts(self, mock_pos, fake_config, tmp_state_dir, thesis_doc):
        write_state_file(tmp_state_dir, "weekly_thesis.json", thesis_doc)
        result = run_price_check(fake_config)
        assert result["aborts"] == 0


class TestPriceCheckAdverseMoves:
    @patch("titantrade.price_check.close_position_at_market")
    @patch("titantrade.price_check.cancel_all_orders_for_ticker")
    @patch("titantrade.price_check._fetch_spy_quote", return_value=0.5)
    @patch("titantrade.price_check.get_positions")
    def test_moderate_3pct_drop_does_NOT_abort_anymore(
        self, mock_pos, mock_spy, mock_cancel, mock_close,
        fake_config, tmp_state_dir, thesis_doc,
    ):
        """price_check has no news context so it can't confirm noise vs real
        breakdown. After the Bug-#3 fix it only fires on catastrophic >=5%
        moves; moderate 3-5% moves wait for the next sentry pass with news.
        """
        mock_pos.return_value = [
            {
                "symbol": "AAPL",
                "qty": "50",
                "current_price": "179.00",  # -3.5% from 185.50 — moderate
                "avg_entry_price": "185.50",
            },
        ]
        write_state_file(tmp_state_dir, "weekly_thesis.json", thesis_doc)
        result = run_price_check(fake_config)
        assert result["aborts"] == 0  # waits for sentry to confirm
        mock_close.assert_not_called()

    @patch("titantrade.price_check.close_position_at_market")
    @patch("titantrade.price_check.cancel_all_orders_for_ticker")
    @patch("titantrade.price_check._fetch_spy_quote", return_value=0.5)
    @patch("titantrade.price_check.get_positions")
    def test_catastrophic_5pct_drop_DOES_abort(
        self, mock_pos, mock_spy, mock_cancel, mock_close,
        fake_config, tmp_state_dir, thesis_doc,
    ):
        """A catastrophic >=5% move still aborts immediately — too dangerous
        to wait for the next sentry pass.
        """
        mock_pos.return_value = [
            {
                "symbol": "AAPL",
                "qty": "50",
                "current_price": "175.00",  # -5.7% from 185.50 — catastrophic
                "avg_entry_price": "185.50",
            },
        ]
        write_state_file(tmp_state_dir, "weekly_thesis.json", thesis_doc)
        result = run_price_check(fake_config)
        assert result["aborts"] == 1
        mock_cancel.assert_called_once()
        mock_close.assert_called_once()

    @patch("titantrade.price_check.close_position_at_market")
    @patch("titantrade.price_check.cancel_all_orders_for_ticker")
    @patch("titantrade.price_check._fetch_spy_quote", return_value=0.5)
    @patch("titantrade.price_check.get_positions")
    def test_continues_on_small_drop(
        self, mock_pos, mock_spy, mock_cancel, mock_close,
        fake_config, tmp_state_dir, thesis_doc,
    ):
        mock_pos.return_value = [
            {
                "symbol": "AAPL",
                "qty": "50",
                "current_price": "183.00",  # -1.3% from 185.50
                "avg_entry_price": "185.50",
            },
        ]
        write_state_file(tmp_state_dir, "weekly_thesis.json", thesis_doc)
        result = run_price_check(fake_config)
        assert result["aborts"] == 0
        mock_close.assert_not_called()


class TestPriceCheckSpyStress:
    @patch("titantrade.price_check.close_position_at_market")
    @patch("titantrade.price_check.cancel_all_orders_for_ticker")
    @patch("titantrade.price_check._fetch_spy_quote", return_value=-2.5)
    @patch("titantrade.price_check.get_positions")
    def test_spy_drop_aborts_all(
        self, mock_pos, mock_spy, mock_cancel, mock_close,
        fake_config, tmp_state_dir, thesis_doc,
    ):
        mock_pos.return_value = [
            {"symbol": "AAPL", "qty": "50", "current_price": "190.00", "avg_entry_price": "185.50"},
            {"symbol": "NVDA", "qty": "20", "current_price": "300.00", "avg_entry_price": "290.00"},
        ]
        write_state_file(tmp_state_dir, "weekly_thesis.json", thesis_doc)
        result = run_price_check(fake_config)
        assert result["aborts"] == 2
        assert result["market_stress"] is True

    @patch("titantrade.price_check.close_position_at_market")
    @patch("titantrade.price_check.cancel_all_orders_for_ticker")
    @patch("titantrade.price_check._fetch_spy_quote", return_value=-1.0)
    @patch("titantrade.price_check.get_positions")
    def test_spy_small_drop_no_stress(
        self, mock_pos, mock_spy, mock_cancel, mock_close,
        fake_config, tmp_state_dir, thesis_doc,
    ):
        mock_pos.return_value = [
            {"symbol": "AAPL", "qty": "50", "current_price": "190.00", "avg_entry_price": "185.50"},
        ]
        write_state_file(tmp_state_dir, "weekly_thesis.json", thesis_doc)
        result = run_price_check(fake_config)
        assert result["aborts"] == 0
        assert result["market_stress"] is False


class TestPriceCheckSavesResult:
    @patch("titantrade.price_check.close_position_at_market")
    @patch("titantrade.price_check.cancel_all_orders_for_ticker")
    @patch("titantrade.price_check._fetch_spy_quote", return_value=0.5)
    @patch("titantrade.price_check.get_positions")
    def test_saves_signal_file(self, mock_pos, mock_spy, mock_cancel, mock_close, fake_config, tmp_state_dir, thesis_doc):
        mock_pos.return_value = [
            {"symbol": "AAPL", "qty": "50", "current_price": "190.00", "avg_entry_price": "185.50"},
        ]
        write_state_file(tmp_state_dir, "weekly_thesis.json", thesis_doc)
        run_price_check(fake_config)
        path = tmp_state_dir / "pricecheck_signals.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert "generated_at" in data
        assert "spy_change_pct" in data
