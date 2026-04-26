"""PUMS loader and audience filtering."""

from __future__ import annotations

import pandas as pd

from preflight.persona.pums_loader import (
    _generate_synthetic_pums,
    filter_by_audience,
    weighted_sample,
)
from preflight.persona.schema import (
    AgeRange,
    AudienceConstraints,
    GeoConstraint,
    IncomeRange,
)


def test_synthetic_pums_has_expected_columns() -> None:
    df = _generate_synthetic_pums(n=1000, seed=42)
    expected = {"AGEP", "SEX", "SCHL", "PINCP", "ST", "RAC1P", "MAR", "PWGTP"}
    assert expected.issubset(df.columns)
    assert len(df) == 1000


def test_age_filter_respected() -> None:
    df = _generate_synthetic_pums(n=5000, seed=42)
    audience = AudienceConstraints(age_range=AgeRange(min=25, max=54))
    out = filter_by_audience(df, audience)
    assert (out["AGEP"] >= 25).all()
    assert (out["AGEP"] <= 54).all()


def test_gender_filter_respected() -> None:
    df = _generate_synthetic_pums(n=5000, seed=42)
    audience = AudienceConstraints(genders=["female"])
    out = filter_by_audience(df, audience)
    assert (out["SEX"] == 2).all()


def test_income_min_filter_respected() -> None:
    df = _generate_synthetic_pums(n=5000, seed=42)
    audience = AudienceConstraints(income_range=IncomeRange(min=50_000))
    out = filter_by_audience(df, audience)
    assert (out["PINCP"] >= 50_000).all()


def test_education_min_filter_respected() -> None:
    df = _generate_synthetic_pums(n=5000, seed=42)
    audience = AudienceConstraints(education_min="college")
    out = filter_by_audience(df, audience)
    # SCHL codes 21 (bachelor's) and above are college+
    assert (out["SCHL"] >= 21).all()


def test_state_filter_respected() -> None:
    df = _generate_synthetic_pums(n=5000, seed=42)
    audience = AudienceConstraints(geo=GeoConstraint(country="US", states=["NY", "CA"]))
    out = filter_by_audience(df, audience)
    assert set(out["ST"].unique()).issubset({36, 6})  # NY=36, CA=6


def test_weighted_sample_returns_correct_size() -> None:
    df = _generate_synthetic_pums(n=2000, seed=42)
    sample = weighted_sample(df, n=500, seed=42)
    assert len(sample) == 500


def test_weighted_sample_is_deterministic() -> None:
    df = _generate_synthetic_pums(n=2000, seed=42)
    s1 = weighted_sample(df, n=100, seed=99)
    s2 = weighted_sample(df, n=100, seed=99)
    pd.testing.assert_frame_equal(s1, s2)


def test_synthetic_income_education_correlation() -> None:
    """Joint distribution sanity: income should correlate with education rank."""
    df = _generate_synthetic_pums(n=10_000, seed=42)
    edu_rank = df["SCHL"].copy()
    # SCHL is monotonic in education level
    corr = df["PINCP"].corr(edu_rank)
    assert corr > 0.3, f"income/education correlation too weak: {corr}"
