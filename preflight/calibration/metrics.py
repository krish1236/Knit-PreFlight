"""Precision / recall / F1 computation for the calibration harness."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from preflight.calibration.injection.types import (
    ALL_DEFECT_CLASSES,
    ALL_SEVERITIES,
    DefectClass,
    Severity,
)


@dataclass
class Tally:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


@dataclass
class CalibrationResults:
    """Aggregated tallies. `per_class[defect][severity]` is the per-cell tally;
    `per_class_aggregate[defect]` is across severities; `overall` is the macro
    F1 across all (defect, severity) cells."""

    per_class: dict[DefectClass, dict[Severity, Tally]] = field(
        default_factory=lambda: {
            d: {s: Tally() for s in ALL_SEVERITIES} for d in ALL_DEFECT_CLASSES
        }
    )

    def record(
        self,
        *,
        expected: DefectClass | None,
        severity: Severity | None,
        observed: list[DefectClass],
    ) -> None:
        """Tally one calibration row.

        expected=None means the survey was clean and we expect no flags.
        For defect-positive surveys, we credit a true-positive if the
        expected class is in `observed`.
        """
        if expected is None:
            # Clean baseline: any observed flag is a false positive (charged
            # to its own (defect_class, severity='subtle') cell as a hard
            # case — the analyzer flagged something that wasn't planted).
            for cls in observed:
                self.per_class[cls]["subtle"].fp += 1
            return

        sev = severity or "moderate"

        if expected in observed:
            self.per_class[expected][sev].tp += 1
        else:
            self.per_class[expected][sev].fn += 1

        for cls in observed:
            if cls != expected:
                self.per_class[cls][sev].fp += 1

    def per_class_aggregate(self) -> dict[DefectClass, Tally]:
        out: dict[DefectClass, Tally] = {}
        for cls, by_severity in self.per_class.items():
            agg = Tally()
            for sev_tally in by_severity.values():
                agg.tp += sev_tally.tp
                agg.fp += sev_tally.fp
                agg.fn += sev_tally.fn
            out[cls] = agg
        return out

    def overall_macro_f1(self) -> float:
        agg = self.per_class_aggregate()
        f1s = [t.f1 for t in agg.values()]
        return sum(f1s) / len(f1s) if f1s else 0.0

    def to_dict(self) -> dict[str, object]:
        agg = self.per_class_aggregate()
        return {
            "overall_macro_f1": self.overall_macro_f1(),
            "per_class": {
                cls: {
                    "f1": agg[cls].f1,
                    "precision": agg[cls].precision,
                    "recall": agg[cls].recall,
                    "by_severity": {
                        sev: {
                            "f1": t.f1,
                            "precision": t.precision,
                            "recall": t.recall,
                            "tp": t.tp,
                            "fp": t.fp,
                            "fn": t.fn,
                        }
                        for sev, t in self.per_class[cls].items()
                    },
                }
                for cls in self.per_class
            },
        }
