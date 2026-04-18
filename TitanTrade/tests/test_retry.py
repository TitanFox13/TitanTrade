"""Tests for retry.py — jitter, 429 handling, Retry-After, backoff cap.

External HTTP is fully mocked via monkeypatching httpx.Client.request.
No real network calls, no tokens spent.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

import titantrade.retry as retry_mod
from titantrade.retry import (
    MAX_DELAY,
    HTTPError,
    _compute_delay,
    _parse_retry_after,
    fetch_with_retry,
)


# ---------------------------------------------------------------------------
# Helpers: a fake httpx.Response chain
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, status_code: int, headers: dict[str, str] | None = None,
                 json_data: Any = None, text: str | None = None):
        self.status_code = status_code
        self.headers = headers or {}
        self._json = json_data if json_data is not None else {}
        self._text = text

    @property
    def text(self) -> str:
        if self._text is not None:
            return self._text
        if self._json:
            import json as _json
            return _json.dumps(self._json)
        return ""

    def json(self) -> Any:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            req = httpx.Request("GET", "http://example.com")
            raise httpx.HTTPStatusError(
                f"{self.status_code}", request=req,
                response=httpx.Response(self.status_code),
            )


class _FakeClient:
    """Drop-in replacement for httpx.Client returning a canned response sequence."""

    def __init__(self, responses: list[_FakeResponse]):
        self._responses = list(responses)
        self.call_count = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def request(self, method: str, url: str, **kwargs) -> _FakeResponse:
        self.call_count += 1
        if not self._responses:
            raise RuntimeError("No more canned responses")
        return self._responses.pop(0)


def _patch_client(monkeypatch: pytest.MonkeyPatch, responses: list[_FakeResponse]):
    """Make httpx.Client(...) return a _FakeClient with the given responses."""
    client = _FakeClient(responses)

    def _factory(*args, **kwargs):
        return client

    monkeypatch.setattr(retry_mod.httpx, "Client", _factory)
    # Skip real sleeps
    monkeypatch.setattr(retry_mod.time, "sleep", lambda _s: None)
    return client


# ---------------------------------------------------------------------------
# Backoff math
# ---------------------------------------------------------------------------

class TestComputeDelay:
    def test_respects_retry_after(self):
        # Retry-After of 3 -> delay = 3 (capped at MAX_DELAY)
        assert _compute_delay(attempt=1, retry_after=3.0) == 3.0

    def test_retry_after_capped(self):
        assert _compute_delay(attempt=1, retry_after=9999.0) == MAX_DELAY

    def test_exponential_without_retry_after(self, monkeypatch):
        # With jitter random in [0, ceiling], a large attempt gives a ceiling
        # close to MAX_DELAY. We pin random to 1.0 to get the ceiling.
        monkeypatch.setattr(retry_mod.random, "uniform", lambda a, b: b)
        d1 = _compute_delay(1)   # ceiling = 2 * 2^0 = 2
        d2 = _compute_delay(2)   # ceiling = 2 * 2^1 = 4
        d3 = _compute_delay(3)   # ceiling = 2 * 2^2 = 8
        assert d1 == 2.0
        assert d2 == 4.0
        assert d3 == 8.0

    def test_jitter_bounds(self, monkeypatch):
        monkeypatch.setattr(retry_mod.random, "uniform", lambda a, b: a)  # pin low
        assert _compute_delay(3) == 0.0

    def test_cap_enforced(self, monkeypatch):
        monkeypatch.setattr(retry_mod.random, "uniform", lambda a, b: b)
        # attempt=10 would give 2*2^9=1024, but MAX_DELAY caps it
        assert _compute_delay(10) == MAX_DELAY


class TestParseRetryAfter:
    def test_numeric(self):
        assert _parse_retry_after("5") == 5.0
        assert _parse_retry_after("2.5") == 2.5

    def test_none(self):
        assert _parse_retry_after(None) is None
        assert _parse_retry_after("") is None

    def test_http_date_ignored(self):
        assert _parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT") is None


# ---------------------------------------------------------------------------
# 429 handling
# ---------------------------------------------------------------------------

class TestRateLimitRetry:
    def test_429_retries_then_succeeds(self, monkeypatch: pytest.MonkeyPatch):
        responses = [
            _FakeResponse(429, headers={"Retry-After": "1"}),
            _FakeResponse(200, json_data={"ok": True}),
        ]
        client = _patch_client(monkeypatch, responses)
        resp = fetch_with_retry("GET", "http://example.com")
        assert resp.status_code == 200
        assert client.call_count == 2

    def test_429_without_retry_after_still_retries(self, monkeypatch):
        responses = [
            _FakeResponse(429),
            _FakeResponse(200, json_data={"ok": True}),
        ]
        _patch_client(monkeypatch, responses)
        resp = fetch_with_retry("GET", "http://example.com")
        assert resp.status_code == 200

    def test_429_exhausts_retries(self, monkeypatch):
        responses = [_FakeResponse(429) for _ in range(10)]
        _patch_client(monkeypatch, responses)
        with pytest.raises(RuntimeError, match="attempts failed"):
            fetch_with_retry("GET", "http://example.com", max_retries=3)


# ---------------------------------------------------------------------------
# 5xx retries
# ---------------------------------------------------------------------------

class TestServerErrorRetry:
    def test_503_then_success(self, monkeypatch):
        responses = [
            _FakeResponse(503),
            _FakeResponse(503),
            _FakeResponse(200, json_data={"v": 1}),
        ]
        client = _patch_client(monkeypatch, responses)
        resp = fetch_with_retry("GET", "http://example.com")
        assert resp.status_code == 200
        assert client.call_count == 3

    def test_500_502_504_529_all_retry(self, monkeypatch):
        for code in (500, 502, 504, 529):
            responses = [
                _FakeResponse(code),
                _FakeResponse(200, json_data={}),
            ]
            _patch_client(monkeypatch, responses)
            resp = fetch_with_retry("GET", "http://example.com")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 4xx (non-429) fails fast
# ---------------------------------------------------------------------------

class TestClientErrorFailFast:
    def test_403_no_retry(self, monkeypatch):
        responses = [
            _FakeResponse(403),
            _FakeResponse(200),  # should not be reached
        ]
        client = _patch_client(monkeypatch, responses)
        with pytest.raises(HTTPError) as exc_info:
            fetch_with_retry("GET", "http://example.com")
        assert client.call_count == 1
        assert exc_info.value.status_code == 403

    def test_404_no_retry(self, monkeypatch):
        responses = [_FakeResponse(404), _FakeResponse(200)]
        client = _patch_client(monkeypatch, responses)
        with pytest.raises(HTTPError):
            fetch_with_retry("GET", "http://example.com")
        assert client.call_count == 1


class TestHTTPErrorBodyCapture:
    """The HTTPError must carry the raw body and parsed JSON so callers can
    branch on service-specific codes (e.g. Alpaca 40310000 for qty race).
    """

    def test_alpaca_qty_error_exposes_code(self, monkeypatch):
        alpaca_body = {
            "code": 40310000,
            "available": "0",
            "existing_qty": "121",
            "held_for_orders": "121",
            "message": "insufficient qty available for order (requested: 121, available: 0)",
            "related_orders": ["abc-123"],
            "symbol": "FCX",
        }
        responses = [_FakeResponse(403, json_data=alpaca_body)]
        _patch_client(monkeypatch, responses)

        with pytest.raises(HTTPError) as exc_info:
            fetch_with_retry("POST", "https://paper-api.alpaca.markets/v2/orders")

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.error_code == 40310000
        assert "insufficient qty" in (exc.error_message or "")
        assert isinstance(exc.data, dict)
        assert exc.data["held_for_orders"] == "121"

    def test_non_json_body_still_usable(self, monkeypatch):
        responses = [_FakeResponse(403, text="Forbidden")]
        _patch_client(monkeypatch, responses)

        with pytest.raises(HTTPError) as exc_info:
            fetch_with_retry("GET", "http://example.com")

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.body == "Forbidden"
        assert exc.error_code is None
        assert exc.error_message is None

    def test_error_message_includes_body_snippet(self, monkeypatch):
        responses = [_FakeResponse(403, json_data={"message": "bad request"})]
        _patch_client(monkeypatch, responses)

        with pytest.raises(HTTPError) as exc_info:
            fetch_with_retry("GET", "http://example.com")

        # The stringified exception should include the body so logs are useful
        assert "bad request" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Success paths
# ---------------------------------------------------------------------------

class TestSuccess:
    def test_immediate_200(self, monkeypatch):
        responses = [_FakeResponse(200, json_data={"x": 1})]
        client = _patch_client(monkeypatch, responses)
        resp = fetch_with_retry("GET", "http://example.com")
        assert resp.status_code == 200
        assert client.call_count == 1

    def test_3xx_returned_without_retry(self, monkeypatch):
        # The function returns on any <400 status (redirects are transparent).
        responses = [_FakeResponse(301)]
        client = _patch_client(monkeypatch, responses)
        resp = fetch_with_retry("GET", "http://example.com")
        assert resp.status_code == 301
        assert client.call_count == 1


# ---------------------------------------------------------------------------
# Network errors
# ---------------------------------------------------------------------------

class TestNetworkErrors:
    def test_connection_error_retries(self, monkeypatch):
        class _BoomClient:
            def __init__(self):
                self.count = 0

            def __enter__(self): return self
            def __exit__(self, *a): return False

            def request(self, *args, **kwargs):
                self.count += 1
                if self.count < 2:
                    raise httpx.ConnectError("boom")
                return _FakeResponse(200, json_data={})

        client = _BoomClient()
        monkeypatch.setattr(retry_mod.httpx, "Client", lambda *a, **k: client)
        monkeypatch.setattr(retry_mod.time, "sleep", lambda _s: None)

        resp = fetch_with_retry("GET", "http://example.com")
        assert resp.status_code == 200
        assert client.count == 2

    def test_timeout_gives_up_after_max_retries(self, monkeypatch):
        class _AlwaysTimeoutClient:
            def __init__(self): self.count = 0
            def __enter__(self): return self
            def __exit__(self, *a): return False

            def request(self, *args, **kwargs):
                self.count += 1
                raise httpx.ReadTimeout("too slow")

        client = _AlwaysTimeoutClient()
        monkeypatch.setattr(retry_mod.httpx, "Client", lambda *a, **k: client)
        monkeypatch.setattr(retry_mod.time, "sleep", lambda _s: None)

        with pytest.raises(RuntimeError, match="attempts failed"):
            fetch_with_retry("GET", "http://example.com", max_retries=3)
        assert client.count == 3
