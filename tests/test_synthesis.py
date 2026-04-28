"""Synthesis recipe sanity: each defect class produces the expected signature."""

from __future__ import annotations

import uuid
from collections import defaultdict

import numpy as np

from preflight.calibration.corpus.seed_surveys import generate_clean_corpus
from preflight.calibration.synthesis import synthesize_response_matrix


def _values_at(rows, question_id, paraphrase_idx):
    return np.array(
        [
            r["response_value"]["response_value"]
            for r in rows
            if r["question_id"] == question_id and r["paraphrase_idx"] == paraphrase_idx
        ],
        dtype=float,
    )


def test_clean_question_responses_are_centered() -> None:
    survey = generate_clean_corpus(n=1, seed=0)[0]
    rows = synthesize_response_matrix(
        run_id=uuid.uuid4(),
        survey=survey,
        affected_question_ids=(),
        defect_class=None,
        n_baseline_personas=400,
        n_sub_swarm=100,
        seed=1,
    )
    q1 = _values_at(rows, "Q1", 0)
    assert 2.5 < q1.mean() < 3.5


def test_leading_wording_creates_paraphrase_shift() -> None:
    survey = generate_clean_corpus(n=1, seed=0)[0]
    rows = synthesize_response_matrix(
        run_id=uuid.uuid4(),
        survey=survey,
        affected_question_ids=("Q1",),
        defect_class="leading_wording",
        n_baseline_personas=400,
        n_sub_swarm=100,
        seed=2,
    )
    original = _values_at(rows, "Q1", 0)
    paraphrase = _values_at(rows, "Q1", 1)
    assert original.mean() - paraphrase.mean() > 0.7


def test_redundant_pair_creates_correlated_responses() -> None:
    survey = generate_clean_corpus(n=1, seed=0)[0]
    rows = synthesize_response_matrix(
        run_id=uuid.uuid4(),
        survey=survey,
        affected_question_ids=("Q1", "Q3"),
        defect_class="redundant_pair",
        n_baseline_personas=400,
        n_sub_swarm=100,
        seed=3,
    )
    a = _values_at(rows, "Q1", 0)
    b = _values_at(rows, "Q3", 0)
    if a.std() == 0 or b.std() == 0:
        return
    corr = float(np.corrcoef(a, b)[0, 1])
    assert corr > 0.7, f"correlation too low: {corr:.2f}"


def test_clean_questions_carry_no_correlation() -> None:
    survey = generate_clean_corpus(n=1, seed=0)[0]
    rows = synthesize_response_matrix(
        run_id=uuid.uuid4(),
        survey=survey,
        affected_question_ids=(),
        defect_class=None,
        n_baseline_personas=600,
        n_sub_swarm=100,
        seed=4,
    )
    a = _values_at(rows, "Q1", 0)
    b = _values_at(rows, "Q3", 0)
    if a.std() == 0 or b.std() == 0:
        return
    corr = abs(float(np.corrcoef(a, b)[0, 1]))
    assert corr < 0.3, f"expected near-zero correlation between clean items, got {corr:.2f}"


def test_row_count_matches_expected() -> None:
    survey = generate_clean_corpus(n=1, seed=0)[0]
    n_baseline = 100
    n_sub = 30
    n_paraphrases = 5
    n_questions = len(survey.questions)
    rows = synthesize_response_matrix(
        run_id=uuid.uuid4(),
        survey=survey,
        affected_question_ids=(),
        defect_class=None,
        n_baseline_personas=n_baseline,
        n_sub_swarm=n_sub,
        n_paraphrases=n_paraphrases,
        seed=5,
    )
    expected = n_questions * (n_baseline + n_paraphrases * n_sub)
    assert len(rows) == expected


def test_scale_clipping_respects_question_type() -> None:
    survey = generate_clean_corpus(n=1, seed=0)[0]
    rows = synthesize_response_matrix(
        run_id=uuid.uuid4(),
        survey=survey,
        affected_question_ids=("Q2",),
        defect_class="leading_wording",
        n_baseline_personas=200,
        n_sub_swarm=50,
        seed=6,
    )
    by_question_type: dict[str, list[int]] = defaultdict(list)
    type_lookup = {q.id: q.type for q in survey.questions}
    for r in rows:
        by_question_type[type_lookup[r["question_id"]]].append(
            r["response_value"]["response_value"]
        )

    for value in by_question_type["likert_5"]:
        assert 1 <= value <= 5
    for value in by_question_type["nps"]:
        assert 0 <= value <= 10
    for value in by_question_type["top_box"]:
        assert 1 <= value <= 5
