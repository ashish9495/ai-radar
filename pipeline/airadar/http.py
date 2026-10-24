"""HTTP helper with timeouts, retries, exponential backoff and rate-limit handling."""
from __future__ import annotations

import logging
import random
import time
from typing import Any

import httpx

log = logging.getLogger(__name__)

RETRY_STATUSES = {429, 500, 502, 503, 504}


class FetchError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class RateLimited(FetchError):
    pass


class Http:
    def __init__(self, user_agent: str, transport: httpx.BaseTransport | None = None,
                 timeout: float = 20.0, max_retries: int = 3, sleep=time.sleep):
        self.client = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=httpx.Timeout(timeout, connect=10.0),
            follow_redirects=True,
            transport=transport,
        )
        self.max_retries = max_retries
        self._sleep = sleep

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.client.request(method, url, **kwargs)
            except httpx.TransportError as exc:  # DNS, connect, read timeouts
                last_exc = exc
                log.warning("transport error %s %s (attempt %d): %s", method, _safe(url), attempt + 1, type(exc).__name__)
            else:
                if resp.status_code < 400:
                    return resp
                if resp.status_code in RETRY_STATUSES and attempt < self.max_retries:
                    wait = _retry_after(resp) or (2 ** attempt + random.random())
                    log.warning("HTTP %d from %s, retrying in %.1fs", resp.status_code, _safe(url), wait)
                    self._sleep(min(wait, 60))
                    continue
                if resp.status_code == 429:
                    raise RateLimited(f"rate limited by {_safe(url)}", 429)
                raise FetchError(f"HTTP {resp.status_code} from {_safe(url)}", resp.status_code)
            if attempt < self.max_retries:
                self._sleep(2 ** attempt + random.random())
        raise FetchError(f"request failed for {_safe(url)}: {type(last_exc).__name__}")

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def close(self) -> None:
        self.client.close()


def _retry_after(resp: httpx.Response) -> float | None:
    value = resp.headers.get("retry-after")
    if value and value.isdigit():
        return float(value)
    reset = resp.headers.get("x-ratelimit-reset")
    if resp.status_code == 403 and reset and reset.isdigit():  # GitHub
        return max(0.0, float(reset) - time.time())
    return None


def _safe(url: str) -> str:
    """Strip query strings from logged URLs so API keys passed as params never leak."""
    return url.split("?", 1)[0]
