"""Free SEC EDGAR API client.

Replaces the paid SEC-API.io service. Uses two public endpoints:
  - https://www.sec.gov/files/company_tickers.json  (ticker -> CIK mapping)
  - https://data.sec.gov/submissions/CIK{cik}.json  (per-company filings)

SEC requires a descriptive User-Agent including a contact email
(https://www.sec.gov/os/accessing-edgar-data). Set SEC_USER_AGENT in
env to override the default.

Rate limit: 10 requests/sec globally (enforced server-side). Our sequential
watchlist iteration stays well below this.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from titantrade.config import STATE_DIR
from titantrade.logger import get_logger
from titantrade.retry import fetch_with_retry

log = get_logger("sec_edgar")

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_clean}/{doc}"

DEFAULT_UA = "TitanTrade/1.0 (contact@titantrade.local)"

# In-memory CIK cache (loaded from disk on first call)
_cik_cache: dict[str, str] = {}
_cik_map_refreshed: bool = False


def _user_agent() -> str:
    """SEC requires a User-Agent with contact info. Configurable via env."""
    return os.environ.get("SEC_USER_AGENT", DEFAULT_UA)


def _headers() -> dict[str, str]:
    return {"User-Agent": _user_agent(), "Accept": "application/json"}


def _cik_cache_path():
    return STATE_DIR / "cik_cache.json"


def _load_cik_cache() -> dict[str, str]:
    path = _cik_cache_path()
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cik_cache(cache: dict[str, str]) -> None:
    with open(_cik_cache_path(), "w") as f:
        json.dump(cache, f, indent=2)


def _fetch_ticker_map() -> dict[str, str]:
    """Download full ticker→CIK map from SEC. ~10k entries, cached to disk."""
    log.info("Fetching SEC ticker→CIK map")
    try:
        resp = fetch_with_retry("GET", TICKER_MAP_URL, headers=_headers())
        data = resp.json()
    except Exception as exc:
        log.warning(f"SEC ticker map fetch failed: {exc}")
        return {}

    # Response is {"0": {"cik_str": 1045810, "ticker": "NVDA", "title": "..."}, ...}
    result: dict[str, str] = {}
    for _, entry in data.items():
        if isinstance(entry, dict):
            ticker = str(entry.get("ticker", "")).upper()
            cik = entry.get("cik_str")
            if ticker and cik is not None:
                # SEC expects 10-digit zero-padded CIK in URLs
                result[ticker] = str(cik).zfill(10)
    return result


def get_cik(ticker: str) -> str | None:
    """Return the 10-digit CIK for a ticker, or None if unknown.

    The SEC ticker map is fetched at most once per process (one HTTP request
    covers all ~10k US-listed tickers). If the on-disk cache exists, we use
    it and never fetch; otherwise we fetch once and persist.
    """
    global _cik_cache, _cik_map_refreshed
    ticker = ticker.upper()

    if not _cik_cache:
        _cik_cache = _load_cik_cache()

    if ticker in _cik_cache:
        return _cik_cache[ticker]

    # Ticker not in cache. Only refresh from SEC once per process to avoid
    # refetching the full map for every unknown ticker (e.g. tests, typos).
    if not _cik_map_refreshed:
        _cik_map_refreshed = True
        fresh = _fetch_ticker_map()
        if fresh:
            _cik_cache = fresh
            _save_cik_cache(_cik_cache)

    return _cik_cache.get(ticker)


def _fetch_submissions(cik: str) -> dict[str, Any]:
    """Fetch full submissions JSON for a CIK (contains all recent filings)."""
    url = SUBMISSIONS_URL.format(cik=cik)
    resp = fetch_with_retry("GET", url, headers=_headers())
    return resp.json()


def _build_filing_url(cik: str, accession_number: str, primary_doc: str) -> str:
    """Construct the EDGAR HTML URL for a filing.

    accession_number comes as '0000886982-26-000096'; the archive path strips dashes.
    """
    acc_clean = accession_number.replace("-", "")
    # Strip leading zeros from CIK for archive URL (SEC uses un-padded CIK here)
    cik_unpadded = cik.lstrip("0") or "0"
    return ARCHIVE_URL.format(cik=cik_unpadded, acc_no_clean=acc_clean, doc=primary_doc)


def fetch_recent_filings(
    ticker: str,
    form_types: tuple[str, ...] = ("8-K", "10-Q", "10-K"),
    days_back: int = 1,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return recent filings of the specified form types for a ticker.

    Defaults replicate the old SEC-API behaviour: 8-K/10-Q/10-K from the last 24h.
    Returns newest-first, max `limit` entries.
    """
    cik = get_cik(ticker)
    if not cik:
        log.info(f"No CIK found for {ticker}")
        return []

    try:
        data = _fetch_submissions(cik)
    except Exception as exc:
        log.warning(f"EDGAR submissions fetch failed for {ticker}: {exc}")
        return []

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accession = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    descriptions = recent.get("primaryDocDescription", [])

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).date()
    wanted = set(form_types)

    results: list[dict[str, Any]] = []
    for i, form in enumerate(forms):
        if form not in wanted:
            continue
        try:
            filed = datetime.strptime(dates[i], "%Y-%m-%d").date()
        except (ValueError, IndexError):
            continue
        if filed < cutoff:
            # list is newest-first; once we're past the cutoff we can stop.
            break

        results.append({
            "form_type": form,
            "filed_at": dates[i],
            "description": descriptions[i] if i < len(descriptions) else "",
            "url": _build_filing_url(cik, accession[i], primary_docs[i])
                   if i < len(accession) and i < len(primary_docs) else "",
        })
        if len(results) >= limit:
            break

    return results


def fetch_insider_filings(
    ticker: str,
    days_back: int = 30,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return recent Form 4 (insider transaction) filings for a ticker.

    Note: the free EDGAR submissions endpoint does NOT include structured
    reporting-owner names in the metadata. If you need the insider's name you
    must parse the individual Form 4 XML (one extra request per filing). For
    the weekly analyst's purposes, the *existence* and *timing* of insider
    activity is the primary signal, so we leave insider_name blank.
    """
    cik = get_cik(ticker)
    if not cik:
        return []

    try:
        data = _fetch_submissions(cik)
    except Exception as exc:
        log.warning(f"EDGAR Form 4 fetch failed for {ticker}: {exc}")
        return []

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accession = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).date()

    results: list[dict[str, Any]] = []
    for i, form in enumerate(forms):
        if form != "4":
            continue
        try:
            filed = datetime.strptime(dates[i], "%Y-%m-%d").date()
        except (ValueError, IndexError):
            continue
        if filed < cutoff:
            break

        results.append({
            "filed_at": dates[i],
            "insider_name": "",  # not available without parsing XML
            "description": "Form 4 insider transaction",
            "url": _build_filing_url(cik, accession[i], primary_docs[i])
                   if i < len(accession) and i < len(primary_docs) else "",
        })
        if len(results) >= limit:
            break

    return results
