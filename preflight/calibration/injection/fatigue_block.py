"""Inject a fatigue-inducing matrix block mid-survey.

Severity ladder controls how big the matrix is:
  subtle    — 8-item matrix
  moderate  — 12-item matrix
  obvious   — 20-item matrix

The block is appended after the original questions; we reuse the brand /
domain language from the clean survey by riffing on its first ordinal
question to make the block feel topical (otherwise the analyzers see it as
disconnected and don't flag fatigue accurately).
"""

from __future__ import annotations

import random

from preflight.calibration.injection.types import (
    DefectClass,
    InjectionResult,
    Severity,
)
from preflight.schemas.survey import Question, Survey

defect_class: DefectClass = "fatigue_block"

SEVERITY_TO_SIZE: dict[Severity, int] = {
    "subtle": 8,
    "moderate": 12,
    "obvious": 20,
}

ATTRIBUTES = [
    "value", "quality", "design", "trust", "innovation", "service",
    "convenience", "support", "reliability", "safety", "ease of use",
    "modernity", "sophistication", "warmth", "approachability",
    "simplicity", "credibility", "premium-ness", "transparency",
    "consistency", "responsiveness",
]


def inject(clean: Survey, severity: Severity, *, seed: int = 0) -> InjectionResult:
    rng = random.Random(seed)
    size = SEVERITY_TO_SIZE[severity]
    chosen = rng.sample(ATTRIBUTES, k=min(size, len(ATTRIBUTES)))
    if size > len(ATTRIBUTES):
        chosen.extend(rng.choices(ATTRIBUTES, k=size - len(ATTRIBUTES)))

    new_questions = list(clean.questions)
    fatigue_ids: list[str] = []
    for i, attr in enumerate(chosen):
        qid = f"FAT_{i:02d}"
        fatigue_ids.append(qid)
        new_questions.append(
            Question(
                id=qid,
                type="likert_5",
                text=(
                    f"On a scale of 1 to 5, how would you rate the brand on "
                    f"{attr}?"
                ),
                scale_labels=[
                    "Very poor", "Poor", "Average", "Good", "Excellent"
                ],
            )
        )

    new_survey = clean.model_copy(
        update={"id": f"{clean.id}__fatigue_{severity}", "questions": new_questions}
    )
    return InjectionResult(
        defect_class=defect_class,
        severity=severity,
        affected_question_ids=tuple(fatigue_ids),
        survey=new_survey,
        note=f"appended {size}-item matrix",
    )
