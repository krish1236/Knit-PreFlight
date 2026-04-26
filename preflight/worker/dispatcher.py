"""Map job_type → handler and execute with proper session/queue plumbing."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from preflight.db.session import SessionLocal
from preflight.logging import get_logger
from preflight.schemas.run import JobPayload, JobType
from preflight.worker.jobs.paraphrase_gen import handle_gen_paraphrases
from preflight.worker.jobs.persona_pool_job import handle_gen_personas
from preflight.worker.jobs.probe_response import handle_run_probe
from preflight.worker.queue import JobQueue
from preflight.worker.state import set_run_status

logger = get_logger(__name__)

Handler = Callable[[JobPayload, AsyncSession, JobQueue], Awaitable[None]]


async def _not_implemented(payload: JobPayload, session: AsyncSession, queue: JobQueue) -> None:
    """Stub for handlers not yet wired (filled in by Phase 2 commit 2)."""
    logger.warning("job.not_implemented", job_type=payload.job_type, run_id=str(payload.run_id))


HANDLERS: dict[JobType, Handler] = {
    "gen_personas": handle_gen_personas,
    "gen_paraphrases": handle_gen_paraphrases,
    "validate_equivalence": _not_implemented,
    "run_probe": handle_run_probe,
    "analyze": _not_implemented,
}


async def dispatch(payload: JobPayload, queue: JobQueue) -> None:
    handler = HANDLERS.get(payload.job_type)
    if handler is None:
        raise ValueError(f"no handler registered for job_type={payload.job_type}")

    async with SessionLocal() as session:
        try:
            await handler(payload, session, queue)
        except Exception as exc:
            logger.exception(
                "job.failed",
                job_type=payload.job_type,
                run_id=str(payload.run_id),
                error=str(exc),
            )
            await set_run_status(session, payload.run_id, "failed", enforce=False)
            raise
