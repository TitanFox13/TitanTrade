"""HTTP retry logic with exponential backoff."""

from __future__ import annotations

import time
from typing import Any

import httpx

from titantrade.logger import get_logger

log = get_logger("retry")

MAX_RETRIES = 3
BASE_DELAY = 2  # seconds


def fetch_with_retry(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> httpx.Response:
    """Make an HTTP request with exponential backoff on failure.

    Retries up to 3 times on network errors and 5xx responses.
    Raises on 4xx errors immediately (client errors aren't retryable).
    """
    last_exc: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json_body,
                )

            if response.status_code < 500:
                response.raise_for_status()
                return response

            # 5xx - retry
            log.warning(
                f"Server error {response.status_code} on attempt {attempt}/{MAX_RETRIES}: {url}"
            )

        except httpx.HTTPStatusError:
            raise
        except Exception as exc:
            last_exc = exc
            log.warning(f"Request failed on attempt {attempt}/{MAX_RETRIES}: {exc}")

        if attempt < MAX_RETRIES:
            delay = BASE_DELAY ** attempt
            log.info(f"Retrying in {delay}s...")
            time.sleep(delay)

    raise RuntimeError(
        f"All {MAX_RETRIES} attempts failed for {method} {url}"
    ) from last_exc
