"""POST /runs — accept a Knit-shaped survey, persist, enqueue persona job."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from preflight.db.models import Report, Run
from preflight.db.session import SessionLocal, get_session
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


@router.get("/{run_id}/report")
async def get_run_report(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    report = await session.get(Report, run_id)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail="report not yet available — run may still be in progress",
        )
    return report.report_json


async def _sse_events(run_id: uuid.UUID) -> AsyncGenerator[str, None]:
    """Poll Postgres every 2s; emit `status` SSE events when the run advances.

    Closes the stream when the run reaches a terminal state (completed/failed)
    or after a hard timeout (~10 min) to prevent zombie connections.
    """
    last_status: str | None = None
    deadline = asyncio.get_event_loop().time() + 600
    yield f"event: ping\ndata: {json.dumps({'run_id': str(run_id)})}\n\n"

    while asyncio.get_event_loop().time() < deadline:
        async with SessionLocal() as session:
            run = await session.get(Run, run_id)
            if run is None:
                yield f"event: error\ndata: {json.dumps({'detail': 'run not found'})}\n\n"
                return
            if run.status != last_status:
                payload = {
                    "status": run.status,
                    "run_id": str(run_id),
                    "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                }
                yield f"event: status\ndata: {json.dumps(payload)}\n\n"
                last_status = run.status
            if run.status in ("completed", "failed"):
                return
        await asyncio.sleep(2.0)

    yield f"event: timeout\ndata: {json.dumps({'run_id': str(run_id)})}\n\n"


@router.get("/{run_id}/stream")
async def stream_run(run_id: uuid.UUID) -> StreamingResponse:
    return StreamingResponse(
        _sse_events(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
