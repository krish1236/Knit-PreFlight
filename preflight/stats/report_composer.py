"""Compose the final report card from analyzer outputs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from preflight.schemas.report import (
    EstimatedPanelExposure,
    QuestionFlags,
    ReportCard,
)
from preflight.schemas.survey import Survey
from preflight.stats.types import (
    IRTFlag,
    ParaphraseShiftFlag,
    QuotaFeasibility,
    RedundancyFlag,
    ScreenerFlag,
    Severity,
)


SEVERITY_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}


def _max_severity(*values: Severity) -> Severity:
    return max(values, key=lambda s: SEVERITY_RANK[s])  # type: ignore[arg-type]


def compose(
    *,
    run_id: uuid.UUID,
    survey: Survey,
    paraphrase_flags: list[ParaphraseShiftFlag],
    irt_flags: list[IRTFlag],
    redundancy_flags: list[RedundancyFlag],
    screener_flags: list[ScreenerFlag],
    quota_flags: list[QuotaFeasibility],
) -> ReportCard:
    paraphrase_by_id = {f.question_id: f for f in paraphrase_flags}
    irt_by_id = {f.question_id: f for f in irt_flags}

    per_question: list[QuestionFlags] = []
    for q in survey.questions:
        p_flag = paraphrase_by_id.get(q.id)
        irt_flag = irt_by_id.get(q.id)
        severities: list[Severity] = ["none"]
        if p_flag is not None:
            severities.append(p_flag.severity)
        if irt_flag is not None:
            severities.append(irt_flag.severity)
        per_question.append(
            QuestionFlags(
                question_id=q.id,
                question_text=q.text,
                type=q.type,
                severity=_max_severity(*severities),
                paraphrase_shift=p_flag,
                irt=irt_flag,
            )
        )

    high_count = sum(1 for q in per_question if q.severity == "high")
    medium_count = sum(1 for q in per_question if q.severity == "medium")
    flagged = high_count + medium_count

    return ReportCard(
        run_id=run_id,
        survey_id=survey.id,
        completed_at=datetime.now(UTC).isoformat(),
        per_question=per_question,
        redundancy_pairs=redundancy_flags,
        screener_issues=screener_flags,
        quota_feasibility=quota_flags,
        estimated_panel_exposure=EstimatedPanelExposure(
            high_severity_questions=high_count,
            medium_severity_questions=medium_count,
            flagged_question_count=flagged,
        ),
    )
