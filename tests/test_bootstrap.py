"""Bootstrap idempotency contract.

Locks two facts:
  1. The emptiness checks correctly detect populated vs empty tables.
  2. The orchestration is fire-and-forget — schedule_bootstrap returns a
     Task that the lifespan can cancel cleanly on shutdown.
"""

from __future__ import annotations

import asyncio
import inspect
from unittest.mock import patch

import pytest

from preflight import bootstrap


def test_bootstrap_module_exposes_expected_surface() -> None:
    assert callable(bootstrap.bootstrap_if_empty)
    assert callable(bootstrap.schedule_bootstrap)
    assert inspect.iscoroutinefunction(bootstrap.bootstrap_if_empty)


def test_schedule_bootstrap_returns_task_without_blocking() -> None:
    """Lifespan needs schedule_bootstrap to return immediately so
    /health stays responsive.
    """
    async def runner() -> bool:
        with patch.object(bootstrap, "bootstrap_if_empty") as mock:
            async def noop() -> None:
                await asyncio.sleep(0.01)
            mock.return_value = noop()
            task = bootstrap.schedule_bootstrap()
            assert isinstance(task, asyncio.Task)
            assert not task.done()
            await task
            return task.done()

    assert asyncio.run(runner()) is True


def test_bootstrap_each_step_handles_step_errors() -> None:
    """A failure in one step (e.g. precompute) does not block subsequent
    steps. Each step is independent; partial bootstraps are acceptable
    because each step is idempotent on the next deploy.
    """
    call_log: list[str] = []

    async def fake_seed() -> None:
        call_log.append("seed")
        raise RuntimeError("seed boom")

    async def fake_precompute() -> None:
        call_log.append("precompute")

    async def fake_calibrate() -> None:
        call_log.append("calibrate")
        raise RuntimeError("calibrate boom")

    async def runner() -> list[str]:
        with (
            patch.object(bootstrap, "_seed_samples_if_empty", fake_seed),
            patch.object(bootstrap, "_precompute_samples_if_missing", fake_precompute),
            patch.object(bootstrap, "_calibrate_if_missing", fake_calibrate),
        ):
            await bootstrap.bootstrap_if_empty()
        return call_log

    result = asyncio.run(runner())
    assert result == ["seed", "precompute", "calibrate"]


@pytest.mark.parametrize(
    "scalar,expected",
    [(0, False), (1, True), (3, True)],
)
def test_samples_seeded_predicate(scalar: int, expected: bool) -> None:
    class _Result:
        def scalar(self) -> int:
            return scalar

    class _FakeSession:
        async def execute(self, _: object) -> _Result:
            return _Result()

    out = asyncio.run(bootstrap._samples_seeded(_FakeSession()))
    assert out is expected
