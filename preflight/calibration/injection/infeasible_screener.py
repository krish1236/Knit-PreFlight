"""Inject infeasible quota / screener configurations.

Severity ladder controls how restrictive the resulting cell is:
  subtle    — narrow but plausible cell (intersect age + state, ~3% panel)
  moderate  — very narrow cell (~1% panel)
  obvious   — combinatorially impossible cell (state + bucket that doesn't
              match the audience, ~0% panel)
"""

from __future__ import annotations

import random

from preflight.calibration.injection.types import (
    DefectClass,
    InjectionResult,
    Severity,
)
from preflight.schemas.survey import QuotaCell, Survey

defect_class: DefectClass = "infeasible_screener"

SEVERITY_TO_CELL: dict[Severity, dict] = {
    "subtle": {"age_bucket": "65+", "state": "VT"},
    "moderate": {"age_bucket": "65+", "state": "WY", "income_bracket": "high"},
    "obvious": {"age_bucket": "18-24", "income_bracket": "high", "state": "WV"},
}


def inject(clean: Survey, severity: Severity, *, seed: int = 0) -> InjectionResult:
    _ = random.Random(seed)
    cell = SEVERITY_TO_CELL[severity]
    new_quota = QuotaCell(cell=cell, target_n=200)

    quotas = list(clean.quotas) + [new_quota]
    new_survey = clean.model_copy(
        update={"id": f"{clean.id}__quota_{severity}", "quotas": quotas}
    )
    return InjectionResult(
        defect_class=defect_class,
        severity=severity,
        affected_question_ids=(),
        survey=new_survey,
        note=f"injected quota cell {cell}",
    )
