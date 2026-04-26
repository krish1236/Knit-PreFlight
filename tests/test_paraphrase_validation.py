"""Paraphrase validation logic — unit-tested with a stub embedder."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np

from preflight.worker.jobs import paraphrase_gen


def _normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.where(norms == 0, 1, norms)


def test_question_hash_stable() -> None:
    a = paraphrase_gen.question_hash("How satisfied are you?")
    b = paraphrase_gen.question_hash("How satisfied are you?")
    assert a == b


def test_question_hash_changes_with_text() -> None:
    assert paraphrase_gen.question_hash("Q1") != paraphrase_gen.question_hash("Q2")


def test_validate_passes_on_good_set() -> None:
    rng = np.random.default_rng(0)
    base = rng.normal(size=384)
    vectors = [base] + [base + rng.normal(scale=0.1, size=384) for _ in range(5)]
    matrix = _normalize(np.array(vectors))

    with patch("preflight.worker.jobs.paraphrase_gen.embed", return_value=matrix):
        ok, reason = paraphrase_gen._validate_paraphrases(
            "original", ["p1", "p2", "p3", "p4", "p5"]
        )
    assert ok, reason


def test_validate_rejects_low_equivalence() -> None:
    rng = np.random.default_rng(1)
    base = rng.normal(size=384)
    vectors = [base] + [rng.normal(size=384) for _ in range(5)]
    matrix = _normalize(np.array(vectors))

    with patch("preflight.worker.jobs.paraphrase_gen.embed", return_value=matrix):
        ok, reason = paraphrase_gen._validate_paraphrases(
            "original", ["p1", "p2", "p3", "p4", "p5"]
        )
    assert not ok
    assert "equivalence" in reason


def test_validate_rejects_collapsed_paraphrases() -> None:
    rng = np.random.default_rng(2)
    base = rng.normal(size=384)
    p = base + rng.normal(scale=0.05, size=384)
    vectors = [base] + [p for _ in range(5)]
    matrix = _normalize(np.array(vectors))

    with patch("preflight.worker.jobs.paraphrase_gen.embed", return_value=matrix):
        ok, reason = paraphrase_gen._validate_paraphrases(
            "original", ["p1", "p1", "p1", "p1", "p1"]
        )
    assert not ok
    assert "pair_too_similar" in reason
