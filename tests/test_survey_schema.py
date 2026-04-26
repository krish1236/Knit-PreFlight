"""Survey schema validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from preflight.schemas.survey import Survey


def _minimal_survey_dict() -> dict:
    return {
        "id": "test-survey-001",
        "version": "0.1",
        "brief": {
            "objectives": ["measure satisfaction"],
            "audience_criteria": "US adults 25-54",
        },
        "audience": {
            "age_range": {"min": 25, "max": 54},
        },
        "questions": [
            {
                "id": "Q1",
                "type": "likert_5",
                "text": "How satisfied are you with the product?",
                "scale_labels": [
                    "Very dissatisfied",
                    "Dissatisfied",
                    "Neutral",
                    "Satisfied",
                    "Very satisfied",
                ],
            }
        ],
    }


def test_minimal_survey_validates() -> None:
    Survey.model_validate(_minimal_survey_dict())


def test_unknown_question_type_rejected() -> None:
    bad = _minimal_survey_dict()
    bad["questions"][0]["type"] = "voice_recording"
    with pytest.raises(ValidationError):
        Survey.model_validate(bad)


def test_extra_top_level_field_rejected() -> None:
    bad = _minimal_survey_dict()
    bad["sneaky_extra"] = "value"
    with pytest.raises(ValidationError):
        Survey.model_validate(bad)


def test_conditional_on_parsed() -> None:
    s = _minimal_survey_dict()
    s["questions"].append(
        {
            "id": "Q2",
            "type": "open_end",
            "text": "Why?",
            "conditional_on": {"q_id": "Q1", "operator": ">=", "value": 4},
        }
    )
    survey = Survey.model_validate(s)
    cond = survey.questions[1].conditional_on
    assert cond is not None
    assert cond.q_id == "Q1"
    assert cond.operator == ">="
    assert cond.value == 4
