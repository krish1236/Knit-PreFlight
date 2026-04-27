"""Quota Monte Carlo feasibility analyzer."""

from __future__ import annotations

from preflight.persona.schema import (
    AgeRange,
    AudienceConstraints,
    GeoConstraint,
)
from preflight.schemas.survey import QuotaCell, Survey
from preflight.stats.analyzers import quota_montecarlo


def _survey(audience: AudienceConstraints, quotas: list[QuotaCell]) -> Survey:
    return Survey.model_validate(
        {
            "id": "q-test",
            "version": "0.1",
            "brief": {"objectives": ["test"], "audience_criteria": "x"},
            "audience": audience.model_dump(),
            "questions": [
                {"id": "Q1", "type": "likert_5", "text": "?"},
            ],
            "quotas": [q.model_dump() for q in quotas],
        }
    )


def test_no_quotas_returns_empty() -> None:
    survey = _survey(AudienceConstraints(), [])
    assert quota_montecarlo.analyze(survey) == []


def test_wide_audience_wide_cell_is_feasible() -> None:
    survey = _survey(
        AudienceConstraints(),
        [QuotaCell(cell={"age_bucket": "25-34"}, target_n=200)],
    )
    out = quota_montecarlo.analyze(survey)
    assert len(out) == 1
    # 25-34 bucket should pull a meaningful chunk of US adults
    assert out[0].estimated_panel_pct > 5
    assert out[0].severity in ("none", "medium")


def test_intersecting_constraints_can_be_infeasible() -> None:
    """A narrow audience + a narrow cell within a single state should be tiny."""
    audience = AudienceConstraints(
        age_range=AgeRange(min=25, max=34),
        geo=GeoConstraint(country="US", states=["WY"]),
    )
    survey = _survey(
        audience,
        [QuotaCell(cell={"age_bucket": "55-64"}, target_n=200)],
    )
    out = quota_montecarlo.analyze(survey)
    # 55-64 bucket contradicts 25-34 audience, so cell pct should be 0
    assert out[0].estimated_panel_pct == 0.0
    assert out[0].severity == "high"


def test_unknown_cell_keys_logged_not_crashed() -> None:
    survey = _survey(
        AudienceConstraints(),
        [QuotaCell(cell={"made_up_key": "value", "age_bucket": "25-34"}, target_n=100)],
    )
    out = quota_montecarlo.analyze(survey)
    assert len(out) == 1
    assert out[0].estimated_panel_pct > 0  # age_bucket still applied
