"""Inject leading-wording defects into a clean survey.

Severity ladder:
  subtle    — soft framing prefix ("would you say...")
  moderate  — social-proof framing ("many people feel that...")
  obvious   — explicit pressure ("isn't it clear that...", "obviously you'd
              agree that...")

Targets ordinal questions (likert / nps / top_box). The first eligible
question past the seed offset gets rewritten in place.
"""

from __future__ import annotations

import random

from preflight.calibration.injection.types import (
    DefectClass,
    InjectionResult,
    Severity,
)
from preflight.schemas.survey import Survey

defect_class: DefectClass = "leading_wording"

PREFIXES: dict[Severity, list[str]] = {
    "subtle": [
        "Would you say that ",
        "How much would you say ",
        "To what extent would you agree that ",
    ],
    "moderate": [
        "Many people feel that ",
        "Most users tend to think ",
        "Research suggests that ",
    ],
    "obvious": [
        "Obviously, you would agree that ",
        "Isn't it clear that ",
        "Wouldn't you say that ",
    ],
}

ORDINAL_TYPES = {"likert_5", "likert_7", "nps", "top_box"}


def _lowercase_first(text: str) -> str:
    return text[:1].lower() + text[1:] if text else text


def inject(clean: Survey, severity: Severity, *, seed: int = 0) -> InjectionResult:
    rng = random.Random(seed)
    eligible = [q for q in clean.questions if q.type in ORDINAL_TYPES]
    if not eligible:
        return InjectionResult(
            defect_class=defect_class,
            severity=severity,
            affected_question_ids=(),
            survey=clean,
            note="no eligible ordinal question to lead",
        )

    target = rng.choice(eligible)
    prefix = rng.choice(PREFIXES[severity])

    new_questions = []
    for q in clean.questions:
        if q.id == target.id:
            new_text = prefix + _lowercase_first(q.text.rstrip("?")) + "?"
            new_questions.append(q.model_copy(update={"text": new_text}))
        else:
            new_questions.append(q)

    new_id = f"{clean.id}__lead_{severity}"
    new_survey = clean.model_copy(update={"id": new_id, "questions": new_questions})
    return InjectionResult(
        defect_class=defect_class,
        severity=severity,
        affected_question_ids=(target.id,),
        survey=new_survey,
        note=f"prefix='{prefix.strip()}'",
    )
