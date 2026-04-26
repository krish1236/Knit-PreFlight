"""Rolling-window circuit breaker for LLM calls.

Trips when failure ratio over the last N calls exceeds a threshold.
Half-open after a cool-down to probe recovery.
"""

from __future__ import annotations

import time
from collections import deque
from enum import Enum
from threading import Lock


class State(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(Exception):
    pass


class CircuitBreaker:
    def __init__(
        self,
        window_size: int = 30,
        failure_ratio_trip: float = 0.5,
        cool_down_seconds: float = 30.0,
        half_open_probes: int = 3,
    ) -> None:
        self._window: deque[bool] = deque(maxlen=window_size)
        self._window_size = window_size
        self._failure_ratio_trip = failure_ratio_trip
        self._cool_down_seconds = cool_down_seconds
        self._half_open_probes = half_open_probes
        self._state = State.CLOSED
        self._opened_at: float = 0.0
        self._half_open_outcomes: list[bool] = []
        self._lock = Lock()

    @property
    def state(self) -> State:
        return self._state

    def before_call(self) -> None:
        with self._lock:
            now = time.monotonic()
            if self._state is State.OPEN:
                if now - self._opened_at >= self._cool_down_seconds:
                    self._state = State.HALF_OPEN
                    self._half_open_outcomes = []
                else:
                    raise CircuitBreakerOpen(
                        f"circuit open; retry in "
                        f"{self._cool_down_seconds - (now - self._opened_at):.1f}s"
                    )

    def record_success(self) -> None:
        with self._lock:
            self._window.append(True)
            if self._state is State.HALF_OPEN:
                self._half_open_outcomes.append(True)
                if len(self._half_open_outcomes) >= self._half_open_probes and all(
                    self._half_open_outcomes
                ):
                    self._state = State.CLOSED
                    self._half_open_outcomes = []

    def record_failure(self) -> None:
        with self._lock:
            self._window.append(False)
            if self._state is State.HALF_OPEN:
                self._open()
                return
            if len(self._window) >= self._window_size:
                failures = sum(1 for ok in self._window if not ok)
                if failures / len(self._window) >= self._failure_ratio_trip:
                    self._open()

    def _open(self) -> None:
        self._state = State.OPEN
        self._opened_at = time.monotonic()
        self._half_open_outcomes = []
