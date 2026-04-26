"""Run state machine — minimal helpers for status transitions.

Allowed transitions:
  pending → personas_ready → paraphrases_ready → probing →
    stats_running → completed
  any → failed
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from preflight.db.models import Run
from preflight.schemas.run import RunStatus

ALLOWED_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    "pending": {"personas_ready", "failed"},
    "personas_ready": {"paraphrases_ready", "failed"},
    "paraphrases_ready": {"probing", "failed"},
    "probing": {"stats_running", "failed"},
    "stats_running": {"completed", "failed"},
    "completed": set(),
    "failed": set(),
}


class InvalidTransition(Exception):
    pass


def assert_can_transition(current: RunStatus, target: RunStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransition(f"cannot transition from {current!r} to {target!r}")


async def set_run_status(
    session: AsyncSession,
    run_id: uuid.UUID,
    status: RunStatus,
    *,
    enforce: bool = True,
) -> None:
    if enforce:
        run = await session.get(Run, run_id)
        if run is None:
            raise ValueError(f"run {run_id} not found")
        assert_can_transition(run.status, status)  # type: ignore[arg-type]

    values: dict[str, object] = {"status": status}
    if status in ("completed", "failed"):
        values["completed_at"] = datetime.now(UTC)

    await session.execute(update(Run).where(Run.id == run_id).values(**values))
    await session.commit()
