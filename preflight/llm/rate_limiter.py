"""Async token-bucket rate limiter for outbound LLM calls."""

from __future__ import annotations

import asyncio
import time


class TokenBucket:
    """Simple async token bucket. Refills at `rate_per_sec` up to `capacity`."""

    def __init__(self, rate_per_sec: float, capacity: float | None = None) -> None:
        self._rate = rate_per_sec
        self._capacity = capacity if capacity is not None else max(1.0, rate_per_sec)
        self._tokens = self._capacity
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> None:
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                deficit = tokens - self._tokens
                wait = deficit / self._rate
            await asyncio.sleep(wait)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_refill = now
