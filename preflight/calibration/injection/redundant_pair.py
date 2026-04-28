"""Inject a redundant question pair into a clean survey.

A redundant pair asks effectively the same thing twice with different
wording. Subtle severity uses a synonym substitution; obvious is a near-clone.
"""

from __future__ import annotations

import random

from preflight.calibration.injection.types import (
    DefectClass,
    InjectionResult,
    Severity,
)
from preflight.schemas.survey import Survey

defect_class: DefectClass = "redundant_pair"

ORDINAL_TYPES = {"likert_5", "likert_7", "nps", "top_box"}

REPHRASE: dict[Severity, list[tuple[str, str]]] = {
    "subtle": [("satisfied", "content"), ("likely", "inclined"), ("important", "significant")],
    "moderate": [("satisfied", "happy"), ("likely", "willing"), ("important", "valuable")],
    "obvious": [("satisfied", "satisfied"), ("likely", "likely"), ("important", "important")],
}


def _rephrase(text: str, severity: Severity, rng: random.Random) -> str:
    candidates = [(a, b) for a, b in REPHRASE[severity] if a in text.lower()]
    if not candidates:
        prefix = "In other words, " if severity != "obvious" else "Once again, "
        return prefix + text[:1].lower() + text[1:]
    a, b = rng.choice(candidates)
    return text.replace(a, b).replace(a.capitalize(), b.capitalize())


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
    cloned_id = f"{target.id}_redundant"
    cloned_text = _rephrase(target.text, severity, rng)
    cloned = target.model_copy(update={"id": cloned_id, "text": cloned_text})

    new_questions = list(clean.questions)
    insert_at = clean.questions.index(target) + 1
    new_questions.insert(insert_at, cloned)

    new_survey = clean.model_copy(
        update={"id": f"{clean.id}__rdndt_{severity}", "questions": new_questions}
    )
    return InjectionResult(
        defect_class=defect_class,
        severity=severity,
        affected_question_ids=(target.id, cloned_id),
        survey=new_survey,
        note=f"cloned {target.id} -> {cloned_id}",
    )
