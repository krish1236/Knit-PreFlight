"""Registry mapping defect_class -> injector module."""

from __future__ import annotations

from collections.abc import Callable

from preflight.calibration.injection import (
    double_barreled,
    fatigue_block,
    infeasible_screener,
    leading_wording,
    loaded_language,
    redundant_pair,
)
from preflight.calibration.injection.types import (
    ALL_DEFECT_CLASSES,
    DefectClass,
    InjectionResult,
    Severity,
)
from preflight.schemas.survey import Survey

InjectFn = Callable[[Survey, Severity, int], InjectionResult]

_REGISTRY: dict[DefectClass, InjectFn] = {
    "leading_wording": lambda s, sev, seed: leading_wording.inject(s, sev, seed=seed),
    "double_barreled": lambda s, sev, seed: double_barreled.inject(s, sev, seed=seed),
    "loaded_language": lambda s, sev, seed: loaded_language.inject(s, sev, seed=seed),
    "redundant_pair": lambda s, sev, seed: redundant_pair.inject(s, sev, seed=seed),
    "fatigue_block": lambda s, sev, seed: fatigue_block.inject(s, sev, seed=seed),
    "infeasible_screener": lambda s, sev, seed: infeasible_screener.inject(s, sev, seed=seed),
}


def inject(
    clean: Survey,
    defect_class: DefectClass,
    severity: Severity,
    *,
    seed: int = 0,
) -> InjectionResult:
    fn = _REGISTRY[defect_class]
    return fn(clean, severity, seed)


def all_classes() -> tuple[DefectClass, ...]:
    return ALL_DEFECT_CLASSES
