"""Final report card schema — the artifact returned to the frontend."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from preflight.stats.types import (
    CalibrationDisclosure,
    IRTFlag,
    ParaphraseShiftFlag,
    QuotaFeasibility,
    RedundancyFlag,
    ScreenerFlag,
    Severity,
)


class QuestionFlags(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    question_text: str
    type: str
    severity: Severity
    paraphrase_shift: ParaphraseShiftFlag | None = None
    irt: IRTFlag | None = None


class EstimatedPanelExposure(BaseModel):
    high_severity_questions: int
    medium_severity_questions: int
    flagged_question_count: int
    method: str = "weighted by per-question severity"


class ReportCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: uuid.UUID
    survey_id: str
    completed_at: str
    calibration: CalibrationDisclosure = Field(default_factory=CalibrationDisclosure)
    per_question: list[QuestionFlags]
    redundancy_pairs: list[RedundancyFlag] = Field(default_factory=list)
    screener_issues: list[ScreenerFlag] = Field(default_factory=list)
    quota_feasibility: list[QuotaFeasibility] = Field(default_factory=list)
    estimated_panel_exposure: EstimatedPanelExposure
    framing_disclaimer: str = (
        "Probes used for instrument stress-testing; not population response prediction. "
        "IRT discrimination is relative-within-survey under the probe pool's generative "
        "process; not an absolute psychometric score."
    )
