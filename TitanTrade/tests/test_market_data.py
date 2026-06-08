"""Tests for the market-data layer (FMP replacement + provider abstraction,
ADR 040).

Provider HTTP is mocked via the provider module's ``fetch_with_retry`` — zero
real calls. Covers: the native (Alpaca+FRED+Finnhub) parsing + fail-open paths,
the retained FMP provider, and the facade dispatch.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from titantrade.config import FREDConfig, FinnhubConfig
from titantrade import market_data
from titantrade.data_providers import native, fmp


def _resp(payload):
    m = MagicMock()
    m.json.return_value = payload
    return m


def _with_keys(cfg, fred="fred-key", finnhub="finnhub-key"):
    return dataclasses.replace(
        cfg, fred=FREDConfig(key=fred), finnhub=FinnhubConfig(key=finnhub)
    )


# --- Native: Alpaca bars / price / change / news ----------------------------

class TestAlpacaBars:
    @patch("titantrade.data_providers.native.fetch_with_retry")
    def test_maps_and_orders_oldest_first(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp({"bars": [
            {"t": "2026-05-01T04:00:00Z", "o": 1.0, "h": 2.0, "l": 0.5, "c": 1.5, "v": 100},
            {"t": "2026-05-02T04:00:00Z", "o": 1.5, "h": 2.5, "l": 1.0, "c": 2.0, "v": 200},
        ], "next_page_token": None})
        bars = market_data.get_ohlcv("SPY", fake_config, days=250)
        assert len(bars) == 2
        assert bars[0] == {"date": "2026-05-01", "open": 1.0, "high": 2.0,
                           "low": 0.5, "close": 1.5, "volume": 100}

    @patch("titantrade.data_providers.native.fetch_with_retry")
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
    @patch("titantrade.data_providers.native.fetch_with_retry")
    def test_latest_price(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp({"trade": {"p": 123.45}})
        assert market_data.get_latest_price("AAPL", fake_config) == 123.45

    @patch("titantrade.data_providers.native.fetch_with_retry")
    def test_latest_price_none_on_error(self, mock_fetch, fake_config):
        mock_fetch.side_effect = RuntimeError("boom")
        assert market_data.get_latest_price("AAPL", fake_config) is None

    @patch("titantrade.data_providers.native.fetch_with_retry")
    def test_daily_change_pct(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp({"latestTrade": {"p": 102.0}, "prevDailyBar": {"c": 100.0}})
        assert market_data.get_daily_change_pct("SPY", fake_config) == 2.0


class TestAlpacaNews:
    @patch("titantrade.data_providers.native.fetch_with_retry")
    def test_maps_news_shape(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp({"news": [
            {"headline": "Big news", "summary": "details", "created_at": "2026-06-01T10:00:00Z", "source": "benzinga"},
        ]})
        assert market_data.get_news("AAPL", fake_config) == [
            {"title": "Big news", "snippet": "details",
             "published_at": "2026-06-01T10:00:00Z", "source": "benzinga"},
        ]

    @patch("titantrade.data_providers.native.fetch_with_retry")
    def test_news_empty_on_error(self, mock_fetch, fake_config):
        mock_fetch.side_effect = RuntimeError("boom")
        assert market_data.get_news("AAPL", fake_config) == []


# --- Native: FRED VIX / treasury / economic calendar ------------------------

class TestFred:
    @patch("titantrade.data_providers.native.fetch_with_retry")
    def test_vix(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp({"observations": [{"value": "18.5"}]})
        assert market_data.get_vix(_with_keys(fake_config)) == 18.5

    def test_vix_none_without_key(self, fake_config):
        assert market_data.get_vix(fake_config) is None

    @patch("titantrade.data_providers.native.fetch_with_retry")
    def test_vix_skips_missing_value(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp({"observations": [{"value": "."}]})
        assert market_data.get_vix(_with_keys(fake_config)) is None

    @patch("titantrade.data_providers.native.fetch_with_retry")
    def test_treasury(self, mock_fetch, fake_config):
        mock_fetch.side_effect = [
            _resp({"observations": [{"value": "4.25"}]}),
            _resp({"observations": [{"value": "4.80"}]}),
        ]
        assert market_data.get_treasury_yields(_with_keys(fake_config)) == {
            "yield_10y": 4.25, "yield_2y": 4.80,
        }

    @patch("titantrade.data_providers.native._load_fomc_dates", return_value=[])
    @patch("titantrade.data_providers.native.fetch_with_retry")
    def test_econ_calendar_per_release_window(self, mock_fetch, _fomc, fake_config):
        """Each high-impact release is queried individually; only dates inside
        the window are kept."""
        today = datetime.now(timezone.utc).date()
        soon = (today + timedelta(days=2)).isoformat()
        far = (today + timedelta(days=40)).isoformat()
        mock_fetch.return_value = _resp({"release_dates": [
            {"date": soon}, {"date": far},
        ]})
        events = market_data.get_economic_calendar(_with_keys(fake_config), days_ahead=7)
        assert events, "expected in-window release events"
        # date is now a tz-aware ISO timestamp at the ET release time (8:30 ET)
        assert all(e["date"].startswith(soon) for e in events)
        assert all(not e["date"].startswith(far) for e in events)
        assert all("T08:30:00" in e["date"] for e in events)  # data-release time
        # one event per configured release id
        assert len(events) == len(native._FRED_RELEASE_IDS)

    def test_econ_calendar_empty_without_key(self, fake_config):
        with patch("titantrade.data_providers.native._load_fomc_dates", return_value=[]):
            assert market_data.get_economic_calendar(fake_config) == []

    @patch("titantrade.data_providers.native.fetch_with_retry", return_value=_resp({"release_dates": []}))
    def test_econ_calendar_includes_fomc(self, _mock, fake_config):
        today = datetime.now(timezone.utc).date()
        soon = (today + timedelta(days=3)).isoformat()
        with patch("titantrade.data_providers.native._load_fomc_dates", return_value=[soon]):
            events = market_data.get_economic_calendar(_with_keys(fake_config), days_ahead=7)
        fomc = [e for e in events if "FOMC" in e["event"]]
        assert fomc
        # FOMC must be stamped at 14:00 ET so the macro-blackout 6h window
        # covers the morning execute (the bug this guards against).
        assert "T14:00:00" in fomc[0]["date"] and fomc[0]["date"].startswith(soon)


# --- Native: Finnhub earnings / analyst / sector ----------------------------

class TestFinnhub:
    @patch("titantrade.data_providers.native.fetch_with_retry")
    def test_earnings_dates(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp({"earningsCalendar": [
            {"symbol": "AAPL", "date": "2026-07-30"},
            {"symbol": "AAPL", "date": "2026-10-29"},
            {"symbol": "MSFT", "date": "2026-07-22"},
        ]})
        out = market_data.get_earnings_dates(["AAPL", "MSFT", "NVDA"], _with_keys(fake_config))
        assert out == {"AAPL": "2026-07-30", "MSFT": "2026-07-22", "NVDA": None}

    def test_earnings_dates_none_without_key(self, fake_config):
        assert market_data.get_earnings_dates(["AAPL"], fake_config) == {"AAPL": None}

    @patch("titantrade.data_providers.native.fetch_with_retry")
    def test_analyst_ratings(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp([
            {"period": "2026-06-01", "strongBuy": 10, "buy": 5, "hold": 3, "sell": 1, "strongSell": 0},
        ])
        out = market_data.get_analyst_ratings("AAPL", _with_keys(fake_config))
        assert out["recent_grades"][0]["strong_buy"] == 10

    def test_analyst_ratings_empty_without_key(self, fake_config):
        assert market_data.get_analyst_ratings("AAPL", fake_config) == {}

    @patch("titantrade.data_providers.native.fetch_with_retry")
    def test_sector(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp({"finnhubIndustry": "Technology"})
        assert market_data.get_sector("AAPL", _with_keys(fake_config)) == "Technology"

    def test_sector_unknown_without_key(self, fake_config):
        assert market_data.get_sector("AAPL", fake_config) == "Unknown"


# --- Provider dispatch + retained FMP provider ------------------------------

class TestProviderDispatch:
    def test_default_is_native(self, fake_config):
        with patch("titantrade.data_providers.native.get_latest_price", return_value=1.0) as n, \
             patch("titantrade.data_providers.fmp.get_latest_price", return_value=2.0) as f:
            assert market_data.get_latest_price("AAPL", fake_config) == 1.0
            n.assert_called_once()
            f.assert_not_called()

    def test_fmp_selected_by_config(self, fake_config):
        cfg = dataclasses.replace(fake_config, data_provider="fmp")
        with patch("titantrade.data_providers.native.get_latest_price", return_value=1.0) as n, \
             patch("titantrade.data_providers.fmp.get_latest_price", return_value=2.0) as f:
            assert market_data.get_latest_price("AAPL", cfg) == 2.0
            f.assert_called_once()
            n.assert_not_called()

    def test_unknown_provider_falls_back_to_native(self, fake_config):
        cfg = dataclasses.replace(fake_config, data_provider="bogus")
        with patch("titantrade.data_providers.native.get_vix", return_value=9.9):
            assert market_data.get_vix(cfg) == 9.9


class TestFmpProvider:
    """The legacy FMP provider is retained and still parses correctly."""

    @patch("titantrade.data_providers.fmp.fetch_with_retry")
    def test_fmp_ohlcv_reverses_to_oldest_first(self, mock_fetch, fake_config):
        # FMP returns newest-first
        mock_fetch.return_value = _resp([
            {"date": "2026-05-02", "open": 2, "high": 2, "low": 2, "close": 2, "volume": 2},
            {"date": "2026-05-01", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1},
        ])
        bars = fmp.get_ohlcv("SPY", fake_config)
        assert [b["date"] for b in bars] == ["2026-05-01", "2026-05-02"]

    @patch("titantrade.data_providers.fmp.fetch_with_retry")
    def test_fmp_news_shape(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp([
            {"title": "T", "text": "body", "publishedDate": "2026-06-01", "site": "fmp"},
        ])
        assert fmp.get_news("AAPL", fake_config) == [
            {"title": "T", "snippet": "body", "published_at": "2026-06-01", "source": "fmp"},
        ]

    @patch("titantrade.data_providers.fmp.fetch_with_retry")
    def test_fmp_vix(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp([{"price": 17.2}])
        assert fmp.get_vix(fake_config) == 17.2
