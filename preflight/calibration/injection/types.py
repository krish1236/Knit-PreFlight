"""Defect classes, severity ladder, and the injector protocol.

The defect classes correspond to the PMC 48-bias-type catalog subset that
v0 covers programmatically. Each injector takes a clean survey and
produces a defect-positive variant at the requested severity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from preflight.schemas.survey import Survey

DefectClass = Literal[
    "leading_wording",
    "double_barreled",
    "loaded_language",
    "redundant_pair",
    "fatigue_block",
    "infeasible_screener",
]

Severity = Literal["subtle", "moderate", "obvious"]

ALL_DEFECT_CLASSES: tuple[DefectClass, ...] = (
    "leading_wording",
    "double_barreled",
    "loaded_language",
    "redundant_pair",
    "fatigue_block",
    "infeasible_screener",
)

ALL_SEVERITIES: tuple[Severity, ...] = ("subtle", "moderate", "obvious")


@dataclass(frozen=True)
class InjectionResult:
    """Output of an injector run on a clean survey."""

    defect_class: DefectClass
    severity: Severity
    affected_question_ids: tuple[str, ...]
    survey: Survey
    note: str = ""


class Injector(Protocol):
    """All injector modules expose `inject(clean, severity, seed) -> InjectionResult`."""

    defect_class: DefectClass

    def inject(
        self, clean: Survey, severity: Severity, *, seed: int = 0
    ) -> InjectionResult: ...
