"""Quota feasibility analysis (HP3 — statistical, no LLM).

For each declared quota cell, we estimate the fraction of the matched
audience (from ACS PUMS) that fits both the audience constraints AND the
cell constraints. Sub-1% feasibility on a meaningful target_n is a strong
signal that fielding will struggle to fill that cell.

Cell constraints supported in v0:
  - age_bucket: "18-24" | "25-34" | "35-44" | "45-54" | "55-64" | "65+"
  - gender:     "male" | "female"
  - income_bracket: "low" | "middle" | "high"
  - state:      USPS code

Other keys are accepted but ignored with a logged warning.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from preflight.logging import get_logger
from preflight.persona.pums_loader import (
    STATE_FIPS_TO_USPS,
    filter_by_audience,
    load_pums,
)
from preflight.schemas.survey import QuotaCell, Survey
from preflight.stats.types import QuotaFeasibility, Severity

logger = get_logger(__name__)

INFEASIBLE_PCT = 1.0
MARGINAL_PCT = 5.0

AGE_BUCKETS = {
    "18-24": (18, 24),
    "25-34": (25, 34),
    "35-44": (35, 44),
    "45-54": (45, 54),
    "55-64": (55, 64),
    "65+": (65, 120),
}

INCOME_BANDS = {
    "low": (0, 35_000),
    "lower_middle": (35_000, 60_000),
    "middle": (60_000, 120_000),
    "upper_middle": (120_000, 200_000),
    "high": (200_000, 1_000_000),
}


def _classify(pct: float) -> Severity:
    if pct < INFEASIBLE_PCT:
        return "high"
    if pct < MARGINAL_PCT:
        return "medium"
    return "none"


def _filter_cell(df: pd.DataFrame, cell: dict[str, Any]) -> pd.DataFrame:
    out = df
    for key, raw_value in cell.items():
        if key == "age_bucket":
            band = AGE_BUCKETS.get(str(raw_value))
            if band is None:
                logger.warning("quota.unknown_age_bucket", value=raw_value)
                continue
            out = out[(out["AGEP"] >= band[0]) & (out["AGEP"] <= band[1])]
        elif key == "gender":
            code = 1 if raw_value == "male" else 2 if raw_value == "female" else None
            if code is None:
                logger.warning("quota.unknown_gender", value=raw_value)
                continue
            out = out[out["SEX"] == code]
        elif key == "income_bracket":
            band = INCOME_BANDS.get(str(raw_value))
            if band is None:
                logger.warning("quota.unknown_income_band", value=raw_value)
                continue
            out = out[(out["PINCP"] >= band[0]) & (out["PINCP"] < band[1])]
        elif key == "state":
            usps_to_fips = {v: k for k, v in STATE_FIPS_TO_USPS.items()}
            code = usps_to_fips.get(str(raw_value))
            if code is None:
                logger.warning("quota.unknown_state", value=raw_value)
                continue
            out = out[out["ST"] == code]
        else:
            logger.warning("quota.unknown_cell_key", key=key, value=raw_value)
    return out


def _weighted_fraction(subset: pd.DataFrame, parent: pd.DataFrame) -> float:
    parent_w = float(parent["PWGTP"].sum()) if not parent.empty else 0.0
    subset_w = float(subset["PWGTP"].sum()) if not subset.empty else 0.0
    if parent_w <= 0:
        return 0.0
    return subset_w / parent_w


def _analyze_cell(
    audience_subset: pd.DataFrame, quota: QuotaCell
) -> QuotaFeasibility:
    cell_subset = _filter_cell(audience_subset, quota.cell)
    pct = _weighted_fraction(cell_subset, audience_subset) * 100.0
    severity = _classify(pct)
    cell_label = ", ".join(f"{k}={v}" for k, v in quota.cell.items())
    if severity == "high":
        if pct == 0.0:
            verdict = (
                f"No audience members fit this cell ({cell_label}). The cell "
                f"is fundamentally incompatible with your audience definition."
            )
        else:
            verdict = (
                f"Only {pct:.1f}% of your matched audience fits this cell. "
                f"You'll burn fielding budget without filling target n={quota.target_n}."
            )
    elif severity == "medium":
        verdict = (
            f"{pct:.1f}% of your audience fits this cell — feasible but tight. "
            f"Filling n={quota.target_n} will require oversampling."
        )
    else:
        verdict = (
            f"{pct:.1f}% of your audience fits this cell — comfortable headroom "
            f"for n={quota.target_n}."
        )
    return QuotaFeasibility(
        cell=quota.cell,
        target_n=quota.target_n,
        estimated_panel_pct=pct,
        estimated_n_at_target=int(pct / 100.0 * quota.target_n),
        severity=severity,
        summary=verdict,
    )


def analyze(survey: Survey) -> list[QuotaFeasibility]:
    if not survey.quotas:
        return []
    pums = load_pums()
    audience_subset = filter_by_audience(pums, survey.audience)
    if audience_subset.empty:
        logger.warning("quota.empty_audience")
        return [
            QuotaFeasibility(
                cell=q.cell,
                target_n=q.target_n,
                estimated_panel_pct=0.0,
                estimated_n_at_target=0,
                severity="high",
                summary=(
                    "Audience constraints match no panel rows. Loosen the "
                    "audience definition before fielding."
                ),
            )
            for q in survey.quotas
        ]
    out = [_analyze_cell(audience_subset, q) for q in survey.quotas]
    logger.info(
        "quota.complete",
        n_quotas=len(out),
        n_high=sum(1 for q in out if q.severity == "high"),
    )
    return out
