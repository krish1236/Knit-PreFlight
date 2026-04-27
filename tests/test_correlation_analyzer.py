"""Redundancy correlation analyzer — pure-python sanity tests on the classifier."""

from __future__ import annotations

from preflight.stats.analyzers.correlation import (
    PEARSON_HIGH,
    PEARSON_MED,
    _classify,
)


def test_high_at_threshold() -> None:
    assert _classify(PEARSON_HIGH) == "high"
    assert _classify(PEARSON_HIGH + 0.05) == "high"
    assert _classify(-PEARSON_HIGH) == "high"  # negative correlation also bad


def test_medium_in_band() -> None:
    assert _classify((PEARSON_HIGH + PEARSON_MED) / 2) == "medium"


def test_none_below_threshold() -> None:
    assert _classify(0.5) == "none"
    assert _classify(0.0) == "none"
    assert _classify(-0.4) == "none"
