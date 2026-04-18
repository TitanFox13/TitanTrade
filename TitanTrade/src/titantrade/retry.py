"""HTTP retry logic with exponential backoff, jitter, and 429 handling."""

from __future__ import annotations

import json
import random
import time
from typing import Any

import httpx

from titantrade.logger import get_logger

log = get_logger("retry")


class HTTPError(Exception):
    """A non-retryable HTTP error (typically 4xx) with the full response body.

    Preserves the server's diagnostic JSON (e.g. Alpaca's
    ``{"code": 40310000, "message": "insufficient qty available ..."}``)
    so callers can branch on ``error_code`` instead of parsing strings.
    """

    def __init__(
        self,
        status_code: int,
        body: str,
        url: str,
        method: str = "GET",
    ):
        self.status_code = status_code
        self.body = body or ""
        self.url = url
        self.method = method
        try:
            self.data: Any = json.loads(self.body) if self.body else None
        except (ValueError, TypeError):
            self.data = None

        snippet = self.body[:300] if self.body else "(empty body)"
        super().__init__(f"HTTP {status_code} {method} {url}: {snippet}")

    @property
    def error_code(self) -> int | None:
        """Service-specific error code (e.g. Alpaca 40310000 = insufficient qty)."""
        if isinstance(self.data, dict):
            code = self.data.get("code")
            if isinstance(code, int):
                return code
        return None

    @property
    def error_message(self) -> str | None:
        """Human-readable error message from the response body, if any."""
        if isinstance(self.data, dict):
            msg = self.data.get("message")
            if isinstance(msg, str):
                return msg
        return None

# More aggressive retry policy — was 3 with max 6s total wait.
# Now 5 attempts with capped exponential backoff + jitter, max ~60s total.
MAX_RETRIES = 5
BASE_DELAY = 2.0     # seconds
MAX_DELAY = 30.0     # cap per-attempt delay
DEFAULT_TIMEOUT = 60.0  # was 30.0 — too short for Gemini under load

# Retry 429 (rate limit) like 5xx; 429 should honour Retry-After header.
RETRYABLE_STATUS = {429, 500, 502, 503, 504, 529}

DEFAULT_HEADERS = {
    "User-Agent": "TitanTrade/1.0 (https://github.com)",
    "Accept": "application/json",
}


def _compute_delay(attempt: int, retry_after: float | None = None) -> float:
    """Full-jitter exponential backoff, capped at MAX_DELAY.

    If the server provided Retry-After, respect it but still clamp the cap.
    """
    if retry_after is not None and retry_after > 0:
        return min(retry_after, MAX_DELAY)
    # AWS-style "full jitter": random [0, base * 2^attempt], capped.
    ceiling = min(BASE_DELAY * (2 ** (attempt - 1)), MAX_DELAY)
    return random.uniform(0, ceiling)


def _parse_retry_after(value: str | None) -> float | None:
    """Parse a Retry-After header value (seconds as int, or HTTP date)."""
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        # HTTP-date form is rare here; ignore and fall back to backoff.
        return None


def fetch_with_retry(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = MAX_RETRIES,
) -> httpx.Response:
    """Make an HTTP request with exponential backoff + jitter on failure.

    Retries up to max_retries on:
      - Network/connection errors
      - 5xx server responses (500, 502, 503, 504, 529)
      - 429 Too Many Requests (honours Retry-After if present)

    Raises immediately on other 4xx errors (client errors aren't retryable).

    Backoff: full-jitter exponential, capped at MAX_DELAY seconds per attempt.
    Timeout: default 60s (AI endpoints can be slow under load).
    """
    merged_headers = {**DEFAULT_HEADERS, **(headers or {})}
    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        retry_after: float | None = None
        status_code: int | None = None

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.request(
                    method,
                    url,
                    headers=merged_headers,
                    params=params,
                    json=json_body,
                )

            status_code = response.status_code

            # Success (2xx/3xx)
            if status_code < 400:
                return response

            # 4xx (non-retryable, except 429). Raise with full body so callers
            # can inspect `error_code` / `error_message` instead of a generic
            # "HTTP 403" message.
            if status_code < 500 and status_code != 429:
                raise HTTPError(status_code, response.text, url, method)

            # 429 — honour Retry-After if present
            if status_code == 429:
                retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                log.warning(
                    f"Rate-limited (429) on attempt {attempt}/{max_retries}: {url}"
                    + (f" (Retry-After: {retry_after}s)" if retry_after else "")
                )
            elif status_code in RETRYABLE_STATUS:
                log.warning(
                    f"Server error {status_code} on attempt {attempt}/{max_retries}: {url}"
                )
            else:
                # Other 5xx we don't explicitly list — still retry, be generous.
                log.warning(
                    f"HTTP {status_code} on attempt {attempt}/{max_retries}: {url}"
                )

        except HTTPError:
            # Non-retryable 4xx — propagate with full body preserved
            raise
        except Exception as exc:
            last_exc = exc
            log.warning(f"Request failed on attempt {attempt}/{max_retries}: {exc}")

        if attempt < max_retries:
            delay = _compute_delay(attempt, retry_after)
            log.info(f"Retrying in {delay:.1f}s...")
            time.sleep(delay)

    raise RuntimeError(
        f"All {max_retries} attempts failed for {method} {url}"
    ) from last_exc
