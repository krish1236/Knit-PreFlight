"""Paraphrase-shift analyzer logic — unit-tested with synthetic matrices."""

from __future__ import annotations

import numpy as np

from preflight.stats.analyzers.paraphrase_shift import (
    COHENS_D_HIGH,
    WASSERSTEIN_HIGH,
    _categorical_shift,
    _classify_severity,
    _cohens_d,
    _matched_personas,
    _ordinal_shift,
)


def test_classify_high_when_both_metric_and_d_strong() -> None:
    assert _classify_severity(WASSERSTEIN_HIGH + 0.1, COHENS_D_HIGH + 0.1, is_js=False) == "high"


def test_classify_medium_when_only_metric_high() -> None:
    assert _classify_severity(WASSERSTEIN_HIGH + 0.1, 0.0, is_js=False) == "medium"


def test_classify_none_when_zero_metric() -> None:
    assert _classify_severity(0.0, None, is_js=False) == "none"


def test_cohens_d_zero_for_identical_distributions() -> None:
    a = np.array([3.0, 3.0, 3.0, 3.0, 3.0, 4.0, 4.0])
    b = a.copy()
    assert _cohens_d(a, b) == 0.0


def test_cohens_d_positive_when_a_higher() -> None:
    a = np.array([4.0, 4.0, 5.0, 5.0, 5.0])
    b = np.array([2.0, 2.0, 3.0, 3.0, 3.0])
    d = _cohens_d(a, b)
    assert d is not None and d > 0


def test_matched_personas_intersection() -> None:
    matrix = {
        0: {"p1": 1, "p2": 2, "p3": 3},
        1: {"p1": 1, "p2": 2},
        2: {"p2": 2, "p3": 3},
    }
    matched = _matched_personas(matrix)
    assert matched == {"p2"}


def test_ordinal_shift_zero_when_distributions_identical() -> None:
    """Both arms are constant 3s; pooled variance is 0 so Cohen's d is undefined (None)."""
    matched = {f"p{i}" for i in range(20)}
    matrix = {
        0: {p: {"response_value": 3} for p in matched},
        1: {p: {"response_value": 3} for p in matched},
    }
    score, d, _ = _ordinal_shift(matrix, matched)
    assert score == 0.0
    assert d is None


def test_ordinal_shift_detects_uniform_lift() -> None:
    """Original answers around 2; paraphrase shifts to ~4."""
    rng = np.random.default_rng(0)
    matched = {f"p{i}" for i in range(80)}
    originals = rng.choice([1, 2, 3], size=80)
    paraphrase = rng.choice([3, 4, 5], size=80)
    matrix = {
        0: {p: {"response_value": int(v)} for p, v in zip(matched, originals)},
        1: {p: {"response_value": int(v)} for p, v in zip(matched, paraphrase)},
    }
    score, d, _ = _ordinal_shift(matrix, matched)
    assert score > 1.0  # large Wasserstein on a 1-5 scale
    assert d is not None and d < -0.5  # original mean lower than paraphrase mean


def test_categorical_shift_zero_when_choices_identical() -> None:
    matched = {f"p{i}" for i in range(30)}
    matrix = {
        0: {p: {"response_value": 0} for p in matched},
        1: {p: {"response_value": 0} for p in matched},
    }
    out = _categorical_shift(matrix, matched, n_options=3)
    assert out is not None
    score, _ = out
    assert score == 0.0


def test_categorical_shift_detects_full_swap() -> None:
    matched = {f"p{i}" for i in range(30)}
    matrix = {
        0: {p: {"response_value": 0} for p in matched},
        1: {p: {"response_value": 2} for p in matched},
    }
    out = _categorical_shift(matrix, matched, n_options=3)
    assert out is not None
    score, _ = out
    assert score > 0.5  # JS divergence saturates near sqrt(ln 2) for fully disjoint hist
