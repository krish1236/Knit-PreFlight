"""Inject double-barreled defects.

A double-barreled question asks two things at once on a single answer scale,
making the response uninterpretable.

Severity ladder:
  subtle    — combine two related items ("rate the price and the value")
  moderate  — combine two divergent items ("rate the speed and the design")
  obvious   — cram three items ("rate the speed, design, and customer service")
"""

from __future__ import annotations

import random

from preflight.calibration.injection.types import (
    DefectClass,
    InjectionResult,
    Severity,
)
from preflight.schemas.survey import Survey

defect_class: DefectClass = "double_barreled"

ORDINAL_TYPES = {"likert_5", "likert_7", "nps", "top_box"}

EXTRA_FACETS: dict[Severity, list[list[str]]] = {
    "subtle": [
        ["price"],
        ["overall value"],
        ["affordability"],
    ],
    "moderate": [
        ["customer service"],
        ["speed of delivery"],
        ["packaging design"],
    ],
    "obvious": [
        ["customer service", "shipping speed"],
        ["packaging design", "brand reputation"],
        ["product features", "after-sale support"],
    ],
}


def inject(clean: Survey, severity: Severity, *, seed: int = 0) -> InjectionResult:
    rng = random.Random(seed)
    eligible = [q for q in clean.questions if q.type in ORDINAL_TYPES]
    if not eligible:
        return InjectionResult(
            defect_class=defect_class,
            severity=severity,
            affected_question_ids=(),
            survey=clean,
            note="no eligible ordinal question to barrel",
        )

    target = rng.choice(eligible)
    extras = rng.choice(EXTRA_FACETS[severity])
    new_text = (
        target.text.rstrip("?")
        + " and "
        + " and ".join(extras)
        + "?"
    )

    new_questions = [
        q.model_copy(update={"text": new_text}) if q.id == target.id else q
        for q in clean.questions
    ]
    new_survey = clean.model_copy(
        update={"id": f"{clean.id}__barrel_{severity}", "questions": new_questions}
    )
    return InjectionResult(
        defect_class=defect_class,
        severity=severity,
        affected_question_ids=(target.id,),
        survey=new_survey,
        note=f"extras={extras}",
    )
