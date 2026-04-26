"""POST /runs — accept a Knit-shaped survey, persist, enqueue persona job."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from preflight.db.models import Run
from preflight.db.session import get_session
from preflight.persona.pool_generator import audience_hash
from preflight.persona.schema import ResponseStyleConfig
from preflight.schemas.run import CreateRunRequest, CreateRunResponse, RunStateView
from preflight.schemas.survey import Survey
from preflight.worker.queue import JobQueue

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=CreateRunResponse, status_code=202)
async def create_run(
    body: CreateRunRequest,
    session: AsyncSession = Depends(get_session),
) -> CreateRunResponse:
    try:
        survey = Survey.model_validate(body.survey)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    n = 500 if body.quick_mode else 1000
    seed = 42

    h = audience_hash(survey.audience, ResponseStyleConfig(), n=n, seed=seed)

    run = Run(
        id=uuid.uuid4(),
        survey_id=survey.id,
        survey_json=survey.model_dump(mode="json"),
        status="pending",
        audience_hash=h,
    )
    session.add(run)
    await session.commit()

    queue = JobQueue()
    try:
        await queue.ensure_group()
        await queue.enqueue(
            job_type="gen_personas",
            run_id=run.id,
            args={"n": n, "seed": seed, "quick_mode": body.quick_mode},
        )
    finally:
        await queue.close()

    return CreateRunResponse(
        run_id=run.id, status="pending", stream_url=f"/runs/{run.id}/stream"
    )


@router.get("/{run_id}", response_model=RunStateView)
async def get_run(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> RunStateView:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return RunStateView(
        run_id=run.id,
        survey_id=run.survey_id,
        status=run.status,  # type: ignore[arg-type]
        is_sample=run.is_sample,
        created_at=run.created_at.isoformat() if run.created_at else "",
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
    )
