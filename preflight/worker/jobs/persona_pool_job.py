"""Generate (or load cached) persona pool for a run; advance state."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from preflight.db.models import Run
from preflight.logging import get_logger
from preflight.persona.pool_generator import get_or_create_pool
from preflight.persona.schema import AudienceConstraints, ResponseStyleConfig
from preflight.schemas.run import JobPayload
from preflight.schemas.survey import Survey
from preflight.worker.queue import JobQueue
from preflight.worker.state import set_run_status

logger = get_logger(__name__)


async def handle_gen_personas(
    payload: JobPayload,
    session: AsyncSession,
    queue: JobQueue,
) -> None:
    run = await session.get(Run, payload.run_id)
    if run is None:
        raise ValueError(f"run {payload.run_id} not found")

    survey = Survey.model_validate(run.survey_json)
    audience = AudienceConstraints.model_validate(survey.audience.model_dump())

    n = int(payload.args.get("n", 1000))
    seed = int(payload.args.get("seed", 42))

    personas, cache_hit = await get_or_create_pool(
        session=session,
        audience=audience,
        style_config=ResponseStyleConfig(),
        n=n,
        seed=seed,
    )

    logger.info(
        "job.gen_personas.done",
        run_id=str(payload.run_id),
        cache_hit=cache_hit,
        n=len(personas),
    )

    await set_run_status(session, payload.run_id, "personas_ready")
    await queue.enqueue(
        job_type="gen_paraphrases",
        run_id=payload.run_id,
        args={"audience_hash": run.audience_hash},
    )
