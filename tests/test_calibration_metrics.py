"""Calibration metrics: tally bookkeeping and F1 math."""

from __future__ import annotations

from preflight.calibration.metrics import CalibrationResults, Tally


def test_tally_perfect_recall() -> None:
    t = Tally(tp=10, fp=0, fn=0)
    assert t.precision == 1.0
    assert t.recall == 1.0
    assert t.f1 == 1.0


def test_tally_zero_when_empty() -> None:
    t = Tally()
    assert t.precision == 0.0
    assert t.recall == 0.0
    assert t.f1 == 0.0


def test_results_records_true_positive() -> None:
    r = CalibrationResults()
    r.record(expected="leading_wording", severity="moderate", observed=["leading_wording"])
    cell = r.per_class["leading_wording"]["moderate"]
    assert cell.tp == 1 and cell.fp == 0 and cell.fn == 0


def test_results_records_false_negative() -> None:
    r = CalibrationResults()
    r.record(expected="leading_wording", severity="subtle", observed=[])
    cell = r.per_class["leading_wording"]["subtle"]
    assert cell.fn == 1


def test_results_records_clean_false_positive() -> None:
    r = CalibrationResults()
    r.record(expected=None, severity=None, observed=["leading_wording"])
    cell = r.per_class["leading_wording"]["subtle"]
    assert cell.fp == 1


def test_results_records_misclassification_as_fp_and_fn() -> None:
    r = CalibrationResults()
    r.record(
        expected="leading_wording",
        severity="moderate",
        observed=["double_barreled"],
    )
    leading_cell = r.per_class["leading_wording"]["moderate"]
    barrel_cell = r.per_class["double_barreled"]["moderate"]
    assert leading_cell.fn == 1
    assert barrel_cell.fp == 1


def test_overall_macro_f1_is_mean_of_class_f1() -> None:
    r = CalibrationResults()
    for _ in range(5):
        r.record(expected="leading_wording", severity="moderate", observed=["leading_wording"])
    for _ in range(5):
        r.record(expected="double_barreled", severity="moderate", observed=["double_barreled"])
    f1 = r.overall_macro_f1()
    assert 0.32 < f1 < 0.34, f"expected ~1/3 (perfect on 2 of 6 classes), got {f1}"


def test_to_dict_has_required_shape() -> None:
    r = CalibrationResults()
    r.record(expected="redundant_pair", severity="obvious", observed=["redundant_pair"])
    d = r.to_dict()
    assert "overall_macro_f1" in d
    assert "per_class" in d
    assert "redundant_pair" in d["per_class"]
    assert "by_severity" in d["per_class"]["redundant_pair"]
    assert "obvious" in d["per_class"]["redundant_pair"]["by_severity"]
