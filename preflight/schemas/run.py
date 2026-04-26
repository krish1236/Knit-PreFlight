"""Run lifecycle DTOs and job-payload envelopes."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RunStatus = Literal[
    "pending",
    "personas_ready",
    "paraphrases_ready",
    "probing",
    "stats_running",
    "completed",
    "failed",
]

JobType = Literal[
    "gen_personas",
    "gen_paraphrases",
    "validate_equivalence",
    "run_probe",
    "analyze",
]


class JobPayload(BaseModel):
    """Envelope for everything that flows through the Redis stream."""

    model_config = ConfigDict(extra="forbid")

    job_type: JobType
    run_id: uuid.UUID
    attempt: int = 1
    args: dict[str, Any] = Field(default_factory=dict)


class CreateRunRequest(BaseModel):
    survey: dict[str, Any]
    quick_mode: bool = False


class CreateRunResponse(BaseModel):
    run_id: uuid.UUID
    status: RunStatus
    stream_url: str


class RunStateView(BaseModel):
    run_id: uuid.UUID
    survey_id: str
    status: RunStatus
    is_sample: bool
    created_at: str
    completed_at: str | None
