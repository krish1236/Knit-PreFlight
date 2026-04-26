"""Circuit breaker state transitions."""

import time

import pytest

from preflight.llm.circuit_breaker import CircuitBreaker, CircuitBreakerOpen, State


def test_starts_closed() -> None:
    cb = CircuitBreaker(window_size=10)
    assert cb.state is State.CLOSED


def test_trips_open_at_threshold() -> None:
    cb = CircuitBreaker(window_size=10, failure_ratio_trip=0.5)
    for _ in range(5):
        cb.record_failure()
    for _ in range(5):
        cb.record_failure()
    assert cb.state is State.OPEN


def test_open_blocks_calls() -> None:
    cb = CircuitBreaker(window_size=4, failure_ratio_trip=0.5, cool_down_seconds=10.0)
    for _ in range(4):
        cb.record_failure()
    with pytest.raises(CircuitBreakerOpen):
        cb.before_call()


def test_half_open_after_cooldown() -> None:
    cb = CircuitBreaker(window_size=4, failure_ratio_trip=0.5, cool_down_seconds=0.05)
    for _ in range(4):
        cb.record_failure()
    time.sleep(0.06)
    cb.before_call()
    assert cb.state is State.HALF_OPEN
