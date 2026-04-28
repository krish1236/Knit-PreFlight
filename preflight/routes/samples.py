"""Sample-survey routes.

GET /samples              list available sample surveys with their cached run_id
                          (if any sample has completed at least once)
POST /samples/{slug}/run  run the sample through the pipeline (or return cached
                          run_id if a completed run already exists)
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import case, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from preflight.db.models import Report, Run
from preflight.db.session import get_session
from preflight.persona.pool_generator import audience_hash
from preflight.persona.schema import ResponseStyleConfig
from preflight.schemas.survey import Survey
from preflight.seeds.sample_loader import load_sample_files
from preflight.worker.queue import JobQueue

router = APIRouter(prefix="/samples", tags=["samples"])


class SampleListing(BaseModel):
    slug: str
    survey_id: str
    title: str
    objective: str
    cached_run_id: uuid.UUID | None
    cached_run_status: str | None


class RunSampleResponse(BaseModel):
    run_id: uuid.UUID
    cached: bool
    status: str


def _title_from_objective(survey_dict: dict[str, Any]) -> str:
    objectives = survey_dict.get("brief", {}).get("objectives", [])
    if objectives:
        return str(objectives[0])
    return survey_dict.get("id", "")


@router.get("", response_model=list[SampleListing])
async def list_samples(
    session: AsyncSession = Depends(get_session),
) -> list[SampleListing]:
    # Status priority: prefer the most useful row to show in the listing.
    # A row with status='completed' is the cached report we want to surface;
    # a row with status='failed' is the worst case (it surfaces a misleading
    # red badge in the UI even when other duplicate rows for the same survey
    # have already succeeded). The listing was sorting by created_at and
    # picking up failed duplicates over earlier completed ones.
    status_priority = case(
        (Run.status == "completed", 0),
        (Run.status == "stats_running", 1),
        (Run.status == "probing", 2),
        (Run.status == "paraphrases_ready", 3),
        (Run.status == "personas_ready", 4),
        (Run.status == "pending", 5),
        (Run.status == "failed", 6),
        else_=7,
    )
    listings: list[SampleListing] = []
    for slug, survey_dict in load_sample_files():
        survey_id = survey_dict["id"]
        result = await session.execute(
            select(Run)
            .where(Run.survey_id == survey_id, Run.is_sample.is_(True))
            .order_by(status_priority, desc(Run.completed_at), desc(Run.created_at))
            .limit(1)
        )
        run = result.scalars().first()
        listings.append(
            SampleListing(
                slug=slug,
                survey_id=survey_id,
                title=_title_from_objective(survey_dict),
                objective=survey_dict.get("brief", {}).get("audience_criteria", ""),
                cached_run_id=run.id if run else None,
                cached_run_status=run.status if run else None,
            )
        )
    return listings


@router.post("/{slug}/run", response_model=RunSampleResponse, status_code=202)
async def run_sample(
    slug: str,
    session: AsyncSession = Depends(get_session),
) -> RunSampleResponse:
    matching = [
        (s, doc) for s, doc in load_sample_files() if s == slug
    ]
    if not matching:
        raise HTTPException(status_code=404, detail=f"sample {slug} not found")
    _, survey_dict = matching[0]

    survey = Survey.model_validate(survey_dict)

    completed = await session.execute(
        select(Run)
        .where(
            Run.survey_id == survey.id,
            Run.is_sample.is_(True),
            Run.status == "completed",
        )
        .order_by(desc(Run.completed_at))
        .limit(1)
    )
    cached = completed.scalars().first()
    if cached is not None:
        report = await session.get(Report, cached.id)
        if report is not None:
            return RunSampleResponse(run_id=cached.id, cached=True, status=cached.status)

    # No completed cache. Before creating a new row, check whether a
    # sample run for this survey is already in flight. Without this
    # check, every click on the sample button while the bootstrap
    # precompute is still running creates another duplicate is_sample
    # row, which then breaks single-row queries in precompute_all_samples
    # on the next deploy.
    in_flight_statuses = (
        "pending",
        "personas_ready",
        "paraphrases_ready",
        "probing",
        "stats_running",
    )
    in_flight = await session.execute(
        select(Run)
        .where(
            Run.survey_id == survey.id,
            Run.is_sample.is_(True),
            Run.status.in_(in_flight_statuses),
        )
        .order_by(desc(Run.created_at))
        .limit(1)
    )
    pending_run = in_flight.scalars().first()
    if pending_run is not None:
        return RunSampleResponse(
            run_id=pending_run.id, cached=False, status=pending_run.status
        )

    h = audience_hash(survey.audience, ResponseStyleConfig(), n=1000, seed=42)
    run = Run(
        id=uuid.uuid4(),
        survey_id=survey.id,
        survey_json=survey.model_dump(mode="json"),
        status="pending",
        audience_hash=h,
        is_sample=True,
    )
    session.add(run)
    await session.commit()

    queue = JobQueue()
    try:
        await queue.ensure_group()
        await queue.enqueue(
            job_type="gen_personas",
            run_id=run.id,
            args={"n": 1000, "seed": 42, "is_sample": True},
        )
    finally:
        await queue.close()

    return RunSampleResponse(run_id=run.id, cached=False, status="pending")
