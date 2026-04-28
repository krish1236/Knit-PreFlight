"""Regression tests for the sample-survey precompute path.

These tests are the lock against the two bugs surfaced during the first
local browser test:

  1. paraphrase_cache wasn't populated, so the report-card UI showed
     '<paraphrase>' placeholder instead of real wording text.
  2. analyzer outputs lacked the plain-English `summary` field, so the UI
     showed bare numbers with no interpretation.

Tests run on the seed annotations directly without requiring Postgres.
"""

from __future__ import annotations

import pytest

from preflight.schemas.survey import Survey
from preflight.seeds.precompute_reports import ANNOTATIONS
from preflight.seeds.sample_loader import load_sample_files


def _samples() -> dict[str, dict]:
    return {survey_id: doc for _, doc in load_sample_files() for survey_id in [doc["id"]]}


def test_every_sample_has_an_annotation() -> None:
    samples = _samples()
    for survey_id in samples:
        assert survey_id in ANNOTATIONS, (
            f"sample {survey_id} has no annotation in precompute_reports.ANNOTATIONS"
        )


def test_every_question_has_paraphrase_text() -> None:
    """The bug we missed: precompute didn't write paraphrase_cache, so
    the UI showed placeholders. This test fails if any sample question
    is missing canned paraphrase text.
    """
    samples = _samples()
    for survey_id, survey_dict in samples.items():
        annotation = ANNOTATIONS[survey_id]
        survey = Survey.model_validate(survey_dict)
        for q in survey.questions:
            if q.type in ("open_end", "video_open_end", "stimulus_block"):
                continue  # paraphrase shift skipped for these types
            paraphrases = annotation.paraphrases_by_qid.get(q.id, [])
            assert len(paraphrases) >= 5, (
                f"{survey_id}.{q.id} ({q.type}) has only {len(paraphrases)} "
                f"paraphrase(s); need ≥5 so the report-card UI shows wordings"
            )
            for i, text in enumerate(paraphrases):
                assert text.strip(), f"{survey_id}.{q.id} paraphrase[{i}] is blank"
                assert "<paraphrase>" not in text, (
                    f"{survey_id}.{q.id} paraphrase[{i}] is the placeholder"
                )


def test_paraphrases_differ_from_original() -> None:
    samples = _samples()
    for survey_id, survey_dict in samples.items():
        annotation = ANNOTATIONS[survey_id]
        survey = Survey.model_validate(survey_dict)
        for q in survey.questions:
            paraphrases = annotation.paraphrases_by_qid.get(q.id, [])
            for i, text in enumerate(paraphrases):
                assert text != q.text, (
                    f"{survey_id}.{q.id} paraphrase[{i}] is identical to the original"
                )


def test_affected_questions_are_real() -> None:
    samples = _samples()
    for survey_id, survey_dict in samples.items():
        annotation = ANNOTATIONS[survey_id]
        question_ids = {q["id"] for q in survey_dict["questions"]}
        for affected in annotation.affected_question_ids:
            assert affected in question_ids, (
                f"{survey_id}: affected_question_ids includes {affected!r} "
                f"which doesn't exist in the survey"
            )


@pytest.mark.parametrize(
    "flag_type,fields",
    [
        ("ParaphraseShiftFlag", ["summary"]),
        ("IRTFlag", ["summary"]),
        ("RedundancyFlag", ["summary"]),
        ("ScreenerFlag", ["summary"]),
        ("QuotaFeasibility", ["summary"]),
    ],
)
def test_flag_types_carry_summary_field(flag_type: str, fields: list[str]) -> None:
    """Lock the contract that every flag class carries a `summary` field for
    plain-English interpretation in the UI.
    """
    from preflight.stats import types as stats_types

    cls = getattr(stats_types, flag_type)
    schema_fields = cls.model_fields
    for field_name in fields:
        assert field_name in schema_fields, (
            f"{flag_type} is missing required field {field_name!r}"
        )
