"""Defect injection harness — every injector × every severity."""

from __future__ import annotations

import pytest

from preflight.calibration.corpus.seed_surveys import generate_clean_corpus
from preflight.calibration.injection.registry import all_classes, inject
from preflight.calibration.injection.types import ALL_SEVERITIES
from preflight.schemas.survey import Survey


@pytest.fixture
def clean_survey() -> Survey:
    return generate_clean_corpus(n=1, seed=0)[0]


@pytest.mark.parametrize("defect_class", all_classes())
@pytest.mark.parametrize("severity", ALL_SEVERITIES)
def test_every_injector_produces_valid_survey(
    clean_survey: Survey, defect_class: str, severity: str
) -> None:
    result = inject(clean_survey, defect_class, severity, seed=42)  # type: ignore[arg-type]
    assert result.defect_class == defect_class
    assert result.severity == severity
    Survey.model_validate(result.survey.model_dump())


def test_leading_wording_changes_text(clean_survey: Survey) -> None:
    result = inject(clean_survey, "leading_wording", "obvious", seed=0)
    assert result.affected_question_ids
    target_id = result.affected_question_ids[0]
    original = next(q for q in clean_survey.questions if q.id == target_id)
    new = next(q for q in result.survey.questions if q.id == target_id)
    assert original.text != new.text
    assert any(
        marker in new.text.lower()
        for marker in ("obviously", "isn't it clear", "wouldn't you say")
    )


def test_double_barreled_concatenates_facets(clean_survey: Survey) -> None:
    result = inject(clean_survey, "double_barreled", "obvious", seed=0)
    target_id = result.affected_question_ids[0]
    new = next(q for q in result.survey.questions if q.id == target_id)
    assert " and " in new.text


def test_loaded_language_inserts_charged_phrase(clean_survey: Survey) -> None:
    result = inject(clean_survey, "loaded_language", "obvious", seed=0)
    target_id = result.affected_question_ids[0]
    new = next(q for q in result.survey.questions if q.id == target_id)
    text = new.text.lower()
    assert any(
        kw in text for kw in ("absolute best", "extraordinary", "must-have", "top-rated")
    )


def test_redundant_pair_adds_one_question(clean_survey: Survey) -> None:
    result = inject(clean_survey, "redundant_pair", "moderate", seed=0)
    assert len(result.survey.questions) == len(clean_survey.questions) + 1
    cloned_id = result.affected_question_ids[1]
    assert any(q.id == cloned_id for q in result.survey.questions)


def test_fatigue_block_adds_size_questions(clean_survey: Survey) -> None:
    sub = inject(clean_survey, "fatigue_block", "subtle", seed=0)
    obv = inject(clean_survey, "fatigue_block", "obvious", seed=0)
    assert (
        len(sub.survey.questions) - len(clean_survey.questions) == 8
    ), "subtle severity should add 8 items"
    assert (
        len(obv.survey.questions) - len(clean_survey.questions) == 20
    ), "obvious severity should add 20 items"


def test_infeasible_screener_adds_quota(clean_survey: Survey) -> None:
    result = inject(clean_survey, "infeasible_screener", "obvious", seed=0)
    assert len(result.survey.quotas) == len(clean_survey.quotas) + 1
    new_quota = result.survey.quotas[-1]
    assert "age_bucket" in new_quota.cell


def test_injection_is_deterministic_given_seed(clean_survey: Survey) -> None:
    a = inject(clean_survey, "leading_wording", "moderate", seed=99)
    b = inject(clean_survey, "leading_wording", "moderate", seed=99)
    assert a.affected_question_ids == b.affected_question_ids
    assert a.survey.questions == b.survey.questions


def test_clean_corpus_generates_requested_size() -> None:
    corpus = generate_clean_corpus(n=12, seed=0)
    assert len(corpus) == 12
    survey_ids = {s.id for s in corpus}
    assert len(survey_ids) == len(corpus), "duplicate ids in clean corpus"
    for s in corpus:
        Survey.model_validate(s.model_dump())
