"""Sample-survey file loader: validates the seeds directory parses correctly."""

from __future__ import annotations

import pytest

from preflight.schemas.survey import Survey
from preflight.seeds.sample_loader import load_sample_files


def test_seed_files_parse_as_valid_surveys() -> None:
    samples = load_sample_files()
    assert samples, "seeds/sample_surveys/ should contain at least one survey"
    for slug, doc in samples:
        try:
            Survey.model_validate(doc)
        except Exception as exc:
            pytest.fail(f"sample {slug!r} failed validation: {exc}")


def test_seed_files_have_distinct_survey_ids() -> None:
    samples = load_sample_files()
    survey_ids = [doc["id"] for _, doc in samples]
    assert len(survey_ids) == len(set(survey_ids)), "duplicate survey_id across samples"


def test_defect_bearing_sample_has_expected_red_flags() -> None:
    samples = dict(load_sample_files())
    defect = samples.get("02_defect_bearing_concept_test")
    assert defect is not None, "defect-bearing sample missing"

    questions = defect["questions"]
    texts = " ".join(q["text"].lower() for q in questions)
    assert "obviously" in texts, "expected leading-wording marker in sample"
    assert any(
        "appealing" in q["text"].lower() and "purchase" in q["text"].lower()
        for q in questions
    ), "expected double-barreled marker in sample"
