"""Tests for the unified market-data layer (FMP replacement, ADR 040).

All provider HTTP is mocked via titantrade.market_data.fetch_with_retry —
zero real calls. Verifies each function parses its provider's response into
the exact shape the connectors expect, and degrades gracefully (empty/None)
on missing keys / errors.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from titantrade.config import FREDConfig, FinnhubConfig
from titantrade import market_data


def _resp(payload):
    m = MagicMock()
    m.json.return_value = payload
    return m


def _with_keys(cfg, fred="fred-key", finnhub="finnhub-key"):
    return dataclasses.replace(
        cfg, fred=FREDConfig(key=fred), finnhub=FinnhubConfig(key=finnhub)
    )


# --- Alpaca: bars / price / change / news -----------------------------------

class TestAlpacaBars:
    @patch("titantrade.market_data.fetch_with_retry")
    def test_maps_and_orders_oldest_first(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp({"bars": [
            {"t": "2026-05-01T04:00:00Z", "o": 1.0, "h": 2.0, "l": 0.5, "c": 1.5, "v": 100},
            {"t": "2026-05-02T04:00:00Z", "o": 1.5, "h": 2.5, "l": 1.0, "c": 2.0, "v": 200},
        ], "next_page_token": None})
        bars = market_data.get_ohlcv("SPY", fake_config, days=250)
        assert len(bars) == 2
        assert bars[0]["date"] == "2026-05-01"
        assert bars[0] == {"date": "2026-05-01", "open": 1.0, "high": 2.0,
                           "low": 0.5, "close": 1.5, "volume": 100}

    @patch("titantrade.market_data.fetch_with_retry")
    def test_paginates(self, mock_fetch, fake_config):
        mock_fetch.side_effect = [
            _resp({"bars": [{"t": "2026-05-01T04:00:00Z", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}],
                   "next_page_token": "tok"}),
            _resp({"bars": [{"t": "2026-05-02T04:00:00Z", "o": 2, "h": 2, "l": 2, "c": 2, "v": 2}],
                   "next_page_token": None}),
        ]
        bars = market_data.get_ohlcv("SPY", fake_config)
        assert [b["date"] for b in bars] == ["2026-05-01", "2026-05-02"]
        assert mock_fetch.call_count == 2


class TestAlpacaQuotes:
    @patch("titantrade.market_data.fetch_with_retry")
    def test_latest_price(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp({"trade": {"p": 123.45}})
        assert market_data.get_latest_price("AAPL", fake_config) == 123.45

    @patch("titantrade.market_data.fetch_with_retry")
    def test_latest_price_none_on_error(self, mock_fetch, fake_config):
        mock_fetch.side_effect = RuntimeError("boom")
        assert market_data.get_latest_price("AAPL", fake_config) is None

    @patch("titantrade.market_data.fetch_with_retry")
    def test_daily_change_pct(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp({
            "latestTrade": {"p": 102.0}, "prevDailyBar": {"c": 100.0},
        })
        assert market_data.get_daily_change_pct("SPY", fake_config) == 2.0


class TestAlpacaNews:
    @patch("titantrade.market_data.fetch_with_retry")
    def test_maps_news_shape(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp({"news": [
            {"headline": "Big news", "summary": "details", "created_at": "2026-06-01T10:00:00Z", "source": "benzinga"},
        ]})
        news = market_data.get_news("AAPL", fake_config)
        assert news == [{"title": "Big news", "snippet": "details",
                         "published_at": "2026-06-01T10:00:00Z", "source": "benzinga"}]

    @patch("titantrade.market_data.fetch_with_retry")
    def test_news_empty_on_error(self, mock_fetch, fake_config):
        mock_fetch.side_effect = RuntimeError("boom")
        assert market_data.get_news("AAPL", fake_config) == []


# --- FRED: VIX / treasury / economic calendar -------------------------------

class TestFred:
    @patch("titantrade.market_data.fetch_with_retry")
    def test_vix(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp({"observations": [{"value": "18.5"}]})
        assert market_data.get_vix(_with_keys(fake_config)) == 18.5

    def test_vix_none_without_key(self, fake_config):
        # default fake_config has no FRED key
        assert market_data.get_vix(fake_config) is None

    @patch("titantrade.market_data.fetch_with_retry")
    def test_vix_skips_missing_value(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp({"observations": [{"value": "."}]})
        assert market_data.get_vix(_with_keys(fake_config)) is None

    @patch("titantrade.market_data.fetch_with_retry")
    def test_treasury(self, mock_fetch, fake_config):
        mock_fetch.side_effect = [
            _resp({"observations": [{"value": "4.25"}]}),  # DGS10
            _resp({"observations": [{"value": "4.80"}]}),  # DGS2
        ]
        assert market_data.get_treasury_yields(_with_keys(fake_config)) == {
            "yield_10y": 4.25, "yield_2y": 4.80,
        }

    @patch("titantrade.market_data._load_fomc_dates", return_value=[])
    @patch("titantrade.market_data.fetch_with_retry")
    def test_econ_calendar_filters_keyword_and_window(self, mock_fetch, _fomc, fake_config):
        today = datetime.now(timezone.utc).date()
        soon = (today + timedelta(days=2)).isoformat()
        far = (today + timedelta(days=40)).isoformat()
        mock_fetch.return_value = _resp({"release_dates": [
            {"release_name": "Consumer Price Index", "date": soon},      # in window + keyword
            {"release_name": "Consumer Price Index", "date": far},       # keyword but out of window
            {"release_name": "Some Obscure Index", "date": soon},        # in window, not high-impact
        ]})
        events = market_data.get_economic_calendar(_with_keys(fake_config), days_ahead=7)
        assert len(events) == 1
        assert events[0]["event"] == "Consumer Price Index"
        assert events[0]["date"] == soon

    def test_econ_calendar_empty_without_key(self, fake_config):
        with patch("titantrade.market_data._load_fomc_dates", return_value=[]):
            assert market_data.get_economic_calendar(fake_config) == []

    @patch("titantrade.market_data.fetch_with_retry")
    def test_econ_calendar_includes_fomc(self, mock_fetch, fake_config):
        today = datetime.now(timezone.utc).date()
        soon = (today + timedelta(days=3)).isoformat()
        mock_fetch.return_value = _resp({"release_dates": []})
        with patch("titantrade.market_data._load_fomc_dates", return_value=[soon]):
            events = market_data.get_economic_calendar(_with_keys(fake_config), days_ahead=7)
        assert any("FOMC" in e["event"] for e in events)


# --- Finnhub: earnings / analyst / sector -----------------------------------

class TestFinnhub:
    @patch("titantrade.market_data.fetch_with_retry")
    def test_earnings_dates(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp({"earningsCalendar": [
            {"symbol": "AAPL", "date": "2026-07-30"},
            {"symbol": "AAPL", "date": "2026-10-29"},  # later — first wins
            {"symbol": "MSFT", "date": "2026-07-22"},
        ]})
        out = market_data.get_earnings_dates(["AAPL", "MSFT", "NVDA"], _with_keys(fake_config))
        assert out["AAPL"] == "2026-07-30"
        assert out["MSFT"] == "2026-07-22"
        assert out["NVDA"] is None

    def test_earnings_dates_none_without_key(self, fake_config):
        out = market_data.get_earnings_dates(["AAPL"], fake_config)
        assert out == {"AAPL": None}

    @patch("titantrade.market_data.fetch_with_retry")
    def test_analyst_ratings(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp([
            {"period": "2026-06-01", "strongBuy": 10, "buy": 5, "hold": 3, "sell": 1, "strongSell": 0},
            {"period": "2026-05-01", "strongBuy": 8, "buy": 6, "hold": 4, "sell": 1, "strongSell": 0},
        ])
        out = market_data.get_analyst_ratings("AAPL", _with_keys(fake_config))
        assert out["recent_grades"][0]["strong_buy"] == 10
        assert out["recent_grades"][0]["date"] == "2026-06-01"

    def test_analyst_ratings_empty_without_key(self, fake_config):
        assert market_data.get_analyst_ratings("AAPL", fake_config) == {}

    @patch("titantrade.market_data.fetch_with_retry")
    def test_sector(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp({"finnhubIndustry": "Technology"})
        assert market_data.get_sector("AAPL", _with_keys(fake_config)) == "Technology"

    def test_sector_unknown_without_key(self, fake_config):
        assert market_data.get_sector("AAPL", fake_config) == "Unknown"
