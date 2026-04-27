"""Screener / skip-logic graph analyzer."""

from __future__ import annotations

from preflight.schemas.survey import (
    Conditional,
    Question,
    ScreenerRule,
    Survey,
)
from preflight.stats.analyzers import screener_graph


def _make_survey(questions: list[Question], screener_rules: list[ScreenerRule] | None = None) -> Survey:
    survey_dict = {
        "id": "test",
        "version": "0.1",
        "brief": {
            "objectives": ["test"],
            "audience_criteria": "US adults",
        },
        "audience": {"age_range": {"min": 18, "max": 65}},
        "questions": [q.model_dump() for q in questions],
    }
    if screener_rules:
        survey_dict["screener"] = {"rules": [r.model_dump() for r in screener_rules]}
    return Survey.model_validate(survey_dict)


def test_clean_survey_has_no_flags() -> None:
    survey = _make_survey(
        [
            Question(id="Q1", type="likert_5", text="?"),
            Question(id="Q2", type="open_end", text="?"),
        ]
    )
    flags = screener_graph.analyze(survey)
    assert flags == []


def test_self_loop_detected() -> None:
    survey = _make_survey(
        [
            Question(
                id="Q1",
                type="likert_5",
                text="?",
                conditional_on=Conditional(q_id="Q1", operator=">=", value=4),
            )
        ]
    )
    flags = screener_graph.analyze(survey)
    assert any(f.type == "self_loop" for f in flags)


def test_forward_reference_detected() -> None:
    """Q1 depends on Q2 but Q2 is asked after Q1."""
    survey = _make_survey(
        [
            Question(
                id="Q1",
                type="likert_5",
                text="?",
                conditional_on=Conditional(q_id="Q2", operator="==", value=1),
            ),
            Question(id="Q2", type="single_choice", text="?", options=["A", "B"]),
        ]
    )
    flags = screener_graph.analyze(survey)
    assert any(f.type == "unreachable_question" for f in flags)


def test_unknown_dependency_detected() -> None:
    survey = _make_survey(
        [
            Question(
                id="Q1",
                type="likert_5",
                text="?",
                conditional_on=Conditional(q_id="DOES_NOT_EXIST", operator="==", value=1),
            )
        ]
    )
    flags = screener_graph.analyze(survey)
    assert any(f.type == "dead_branch" for f in flags)


def test_impossible_likert_value_flagged() -> None:
    """Q2 is conditional on Q1 == 99, but Q1 is likert_5 (1-5)."""
    survey = _make_survey(
        [
            Question(id="Q1", type="likert_5", text="?"),
            Question(
                id="Q2",
                type="open_end",
                text="?",
                conditional_on=Conditional(q_id="Q1", operator="==", value=99),
            ),
        ]
    )
    flags = screener_graph.analyze(survey)
    assert any(f.type == "dead_branch" for f in flags)


def test_contradicting_screener_rules() -> None:
    survey = _make_survey(
        [Question(id="S1", type="single_choice", text="?", options=["yes", "no"])],
        screener_rules=[
            ScreenerRule(q_id="S1", if_value_in=[0], action="terminate"),
            ScreenerRule(q_id="S1", if_value_in=[0, 1], action="qualify"),
        ],
    )
    flags = screener_graph.analyze(survey)
    assert any(f.type == "contradicting_rule" for f in flags)
