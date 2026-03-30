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
    resubmit_expired_brackets,
)

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
