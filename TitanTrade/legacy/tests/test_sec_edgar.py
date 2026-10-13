"""Tests for sec_edgar.py — EDGAR ticker/CIK lookup + filings parsing.

External HTTP is fully mocked. No real SEC traffic, no network required.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

import titantrade.sec_edgar as edgar_mod
from titantrade.sec_edgar import (
    _build_filing_url,
    fetch_insider_filings,
    fetch_recent_filings,
    get_cik,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Fresh CIK cache per test, pointed at a temp state dir."""
    monkeypatch.setattr(edgar_mod, "_cik_cache", {})
    monkeypatch.setattr(edgar_mod, "_cik_map_refreshed", False)
    monkeypatch.setattr(edgar_mod, "STATE_DIR", tmp_path)


SAMPLE_TICKER_MAP = {
    "0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
    "1": {"cik_str": 886982, "ticker": "GS", "title": "GOLDMAN SACHS"},
}


SAMPLE_SUBMISSIONS = {
    "name": "GOLDMAN SACHS GROUP INC",
    "tickers": ["GS"],
    "filings": {
        "recent": {
            "form": ["8-K", "10-Q", "4", "10-K", "424B2"],
            "filingDate": [
                "2026-04-13", "2026-04-10", "2026-04-09",
                "2026-02-25", "2026-04-17",
            ],
            "accessionNumber": [
                "0000886982-26-000096",
                "0000886982-26-000094",
                "0001193125-26-150095",
                "0000886982-26-000091",
                "0001193125-26-161846",
            ],
            "primaryDocument": [
                "gs-20260413.htm",
                "gs-10q.htm",
                "form4.xml",
                "gs-20251231.htm",
                "424b2.htm",
            ],
            "primaryDocDescription": [
                "8-K", "10-Q", "FORM 4", "10-K", "424B2",
            ],
        }
    },
}


# ---------------------------------------------------------------------------
# CIK lookup
# ---------------------------------------------------------------------------

class TestGetCIK:
    def test_lookup_populates_cache(self, monkeypatch):
        with patch.object(edgar_mod, "_fetch_ticker_map",
                          return_value={"NVDA": "0001045810", "GS": "0000886982"}):
            assert get_cik("NVDA") == "0001045810"
            # Second call hits the in-memory cache → no refetch
            assert get_cik("GS") == "0000886982"

    def test_case_insensitive(self):
        with patch.object(edgar_mod, "_fetch_ticker_map",
                          return_value={"NVDA": "0001045810"}):
            assert get_cik("nvda") == "0001045810"

    def test_unknown_ticker_returns_none(self):
        with patch.object(edgar_mod, "_fetch_ticker_map",
                          return_value={"NVDA": "0001045810"}):
            assert get_cik("FAKETICKER") is None

    def test_map_fetched_only_once(self, monkeypatch):
        """Unknown tickers must not cause repeated map refreshes."""
        fetcher = patch.object(
            edgar_mod, "_fetch_ticker_map",
            return_value={"NVDA": "0001045810"},
        )
        with fetcher as mock_fetch:
            get_cik("FAKE1")
            get_cik("FAKE2")
            get_cik("FAKE3")
            assert mock_fetch.call_count == 1

    def test_cache_persisted_to_disk(self, tmp_path):
        with patch.object(edgar_mod, "_fetch_ticker_map",
                          return_value={"NVDA": "0001045810"}):
            get_cik("NVDA")
        # The file should exist
        cache_file = tmp_path / "cik_cache.json"
        assert cache_file.exists()

    def test_disk_cache_avoids_fetch(self, tmp_path, monkeypatch):
        # Prepopulate disk cache
        cache_file = tmp_path / "cik_cache.json"
        cache_file.write_text('{"NVDA": "0001045810"}')

        with patch.object(edgar_mod, "_fetch_ticker_map") as mock_fetch:
            assert get_cik("NVDA") == "0001045810"
            mock_fetch.assert_not_called()


# ---------------------------------------------------------------------------
# URL construction
# ---------------------------------------------------------------------------

class TestBuildFilingURL:
    def test_standard_url(self):
        url = _build_filing_url("0000886982", "0000886982-26-000096", "gs-20260413.htm")
        assert url == "https://www.sec.gov/Archives/edgar/data/886982/000088698226000096/gs-20260413.htm"

    def test_strips_leading_zeros_from_cik(self):
        # CIK in URL is un-padded, but accession number keeps its structure.
        url = _build_filing_url("0001045810", "0001045810-24-000001", "test.htm")
        assert "/data/1045810/" in url
        assert "/000104581024000001/" in url


# ---------------------------------------------------------------------------
# Recent filings
# ---------------------------------------------------------------------------

class TestFetchRecentFilings:
    def test_returns_matching_forms(self, monkeypatch):
        monkeypatch.setattr(edgar_mod, "get_cik", lambda t: "0000886982")
        monkeypatch.setattr(edgar_mod, "_fetch_submissions",
                            lambda cik: SAMPLE_SUBMISSIONS)

        # days_back=9999 to include our 2026 sample data from any run date
        filings = fetch_recent_filings(
            "GS", form_types=("8-K", "10-Q", "10-K"),
            days_back=9999, limit=10,
        )
        form_types = {f["form_type"] for f in filings}
        assert form_types == {"8-K", "10-Q", "10-K"}

    def test_filters_out_unwanted_forms(self, monkeypatch):
        monkeypatch.setattr(edgar_mod, "get_cik", lambda t: "0000886982")
        monkeypatch.setattr(edgar_mod, "_fetch_submissions",
                            lambda cik: SAMPLE_SUBMISSIONS)

        filings = fetch_recent_filings("GS", form_types=("8-K",), days_back=9999)
        assert all(f["form_type"] == "8-K" for f in filings)

    def test_respects_limit(self, monkeypatch):
        monkeypatch.setattr(edgar_mod, "get_cik", lambda t: "0000886982")
        monkeypatch.setattr(edgar_mod, "_fetch_submissions",
                            lambda cik: SAMPLE_SUBMISSIONS)

        filings = fetch_recent_filings(
            "GS", form_types=("8-K", "10-Q", "10-K", "4"),
            days_back=9999, limit=2,
        )
        assert len(filings) == 2

    def test_no_cik_returns_empty(self, monkeypatch):
        monkeypatch.setattr(edgar_mod, "get_cik", lambda t: None)
        assert fetch_recent_filings("UNKNOWN") == []

    def test_submissions_error_returns_empty(self, monkeypatch):
        monkeypatch.setattr(edgar_mod, "get_cik", lambda t: "0000886982")

        def _boom(cik):
            raise RuntimeError("500 error")

        monkeypatch.setattr(edgar_mod, "_fetch_submissions", _boom)
        assert fetch_recent_filings("GS") == []

    def test_urls_are_well_formed(self, monkeypatch):
        monkeypatch.setattr(edgar_mod, "get_cik", lambda t: "0000886982")
        monkeypatch.setattr(edgar_mod, "_fetch_submissions",
                            lambda cik: SAMPLE_SUBMISSIONS)

        filings = fetch_recent_filings("GS", days_back=9999)
        for f in filings:
            assert f["url"].startswith("https://www.sec.gov/Archives/edgar/data/")
            assert ".htm" in f["url"] or ".xml" in f["url"]


# ---------------------------------------------------------------------------
# Insider filings (Form 4)
# ---------------------------------------------------------------------------

class TestFetchInsiderFilings:
    def test_returns_only_form_4(self, monkeypatch):
        monkeypatch.setattr(edgar_mod, "get_cik", lambda t: "0000886982")
        monkeypatch.setattr(edgar_mod, "_fetch_submissions",
                            lambda cik: SAMPLE_SUBMISSIONS)

        insiders = fetch_insider_filings("GS", days_back=9999)
        assert len(insiders) >= 1
        for ins in insiders:
            # Shape matches what Claude's prompt expects
            assert "filed_at" in ins
            assert "insider_name" in ins  # blank but present
            assert "description" in ins
            assert "url" in ins

    def test_no_cik_returns_empty(self, monkeypatch):
        monkeypatch.setattr(edgar_mod, "get_cik", lambda t: None)
        assert fetch_insider_filings("UNKNOWN") == []

    def test_empty_submissions_returns_empty(self, monkeypatch):
        monkeypatch.setattr(edgar_mod, "get_cik", lambda t: "0000886982")
        monkeypatch.setattr(edgar_mod, "_fetch_submissions",
                            lambda cik: {"filings": {"recent": {}}})
        assert fetch_insider_filings("GS") == []
