"""Inject loaded-language defects.

Loaded language uses emotionally-charged adjectives that prime a response.

Severity ladder:
  subtle    — single mild emotional adjective
  moderate  — clear charged term
  obvious   — multiple charged terms stacked
"""

from __future__ import annotations

import random

from preflight.calibration.injection.types import (
    DefectClass,
    InjectionResult,
    Severity,
)
from preflight.schemas.survey import Survey

defect_class: DefectClass = "loaded_language"

ORDINAL_TYPES = {"likert_5", "likert_7", "nps", "top_box"}

LOAD_PHRASES: dict[Severity, list[str]] = {
    "subtle": [
        " (which most experts recommend)",
        " (a popular choice)",
        " (a well-regarded option)",
    ],
    "moderate": [
        " (a truly outstanding option)",
        " (an exceptional choice)",
        " (a market leader)",
    ],
    "obvious": [
        " (the absolute best, most-loved, top-rated option)",
        " (an extraordinary, world-class, award-winning choice)",
        " (a superior, premium, must-have option)",
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
            note="no eligible ordinal question",
        )

    target = rng.choice(eligible)
    insertion = rng.choice(LOAD_PHRASES[severity])
    new_text = target.text.rstrip("?") + insertion + "?"

    new_questions = [
        q.model_copy(update={"text": new_text}) if q.id == target.id else q
        for q in clean.questions
    ]
    new_survey = clean.model_copy(
        update={"id": f"{clean.id}__load_{severity}", "questions": new_questions}
    )
    return InjectionResult(
        defect_class=defect_class,
        severity=severity,
        affected_question_ids=(target.id,),
        survey=new_survey,
        note=f"insertion='{insertion.strip()}'",
    )
