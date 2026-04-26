"""Job handler base protocol."""

from __future__ import annotations

from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from preflight.schemas.run import JobPayload
from preflight.worker.queue import JobQueue


class JobHandler(Protocol):
    job_type: str

    async def __call__(
        self,
        payload: JobPayload,
        session: AsyncSession,
        queue: JobQueue,
    ) -> None: ...
