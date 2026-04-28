"""Synthesize a probe-response matrix that mimics what real LLM probes would
produce on a given survey, parameterized by which questions carry which
defect.

Why synthetic instead of real LLM responses for calibration?
- Real LLM calibration: 200 surveys x 6 defects x 3 severities x ~30K probe
  calls = millions of calls. Cost is in the thousands of dollars per run.
- Calibration's purpose is to validate that *the analyzers correctly classify
  defect signatures*. The signatures themselves are well-defined (paraphrase
  shift, low IRT discrimination, high inter-question correlation, etc.).
  Synthesizing the signatures lets us test the analyzers cheaply on every
  commit while keeping the real-LLM end-to-end run as a separate periodic
  spend.

The synthesis is deliberate and documented per defect class so it cannot be
mistaken for a closed-loop test.
"""

from __future__ import annotations

import random
import uuid
from typing import Any

import numpy as np

from preflight.calibration.injection.types import DefectClass
from preflight.schemas.survey import Question, Survey


def _scale_max_for(question: Question) -> int:
    if question.type == "likert_5":
        return 5
    if question.type == "likert_7":
        return 7
    if question.type == "nps":
        return 10
    if question.type == "top_box":
        return 5
    if question.type == "single_choice":
        return max(0, len(question.options or []) - 1)
    return 5


def _clip(values: np.ndarray, lo: int, hi: int) -> np.ndarray:
    return np.clip(np.round(values), lo, hi).astype(int)


def _scale_lo_for(question: Question) -> int:
    return 0 if question.type in ("nps", "single_choice") else 1


def _baseline_distribution(
    question: Question, n: int, rng: np.random.Generator
) -> np.ndarray:
    lo = _scale_lo_for(question)
    hi = _scale_max_for(question)
    mid = (lo + hi) / 2
    width = (hi - lo) / 4
    return _clip(rng.normal(loc=mid, scale=width, size=n), lo, hi)


def _shifted_distribution(
    question: Question,
    n: int,
    rng: np.random.Generator,
    *,
    shift: float,
) -> np.ndarray:
    """Push responses toward the high end (positive shift) or low (negative)."""
    lo = _scale_lo_for(question)
    hi = _scale_max_for(question)
    mid = (lo + hi) / 2
    target = mid + shift * (hi - mid)
    width = max(0.5, (hi - lo) / 6)
    return _clip(rng.normal(loc=target, scale=width, size=n), lo, hi)


def _diluted_distribution(
    question: Question, n: int, rng: np.random.Generator
) -> np.ndarray:
    """Wider variance, low information — mimics double-barreled noise."""
    lo = _scale_lo_for(question)
    hi = _scale_max_for(question)
    return _clip(rng.uniform(low=lo, high=hi + 1, size=n), lo, hi)


def _satisficing_distribution(
    question: Question, n: int, rng: np.random.Generator
) -> np.ndarray:
    """Heavy concentration on the middle option — mimics fatigue satisficing."""
    lo = _scale_lo_for(question)
    hi = _scale_max_for(question)
    mid = (lo + hi) // 2
    return _clip(rng.normal(loc=mid, scale=0.6, size=n), lo, hi)


# Per-defect synthesis recipe. Returns rows formatted for ProbeResponse upserts.
def synthesize_response_matrix(
    *,
    run_id: uuid.UUID,
    survey: Survey,
    affected_question_ids: tuple[str, ...],
    defect_class: DefectClass | None,
    n_baseline_personas: int = 1000,
    n_sub_swarm: int = 200,
    n_paraphrases: int = 5,
    seed: int = 0,
) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)

    baseline_persona_ids = [f"p{i:04d}" for i in range(n_baseline_personas)]
    sub_swarm_ids = baseline_persona_ids[:n_sub_swarm]

    affected = set(affected_question_ids)

    rows: list[dict[str, Any]] = []
    for question in survey.questions:
        is_affected = question.id in affected

        # paraphrase_idx=0 (original wording) — full baseline pool
        baseline_responses = _baseline_response_for(
            question, defect_class, is_affected, n_baseline_personas, rng,
            paraphrase_idx=0,
        )
        for pid, value in zip(baseline_persona_ids, baseline_responses):
            rows.append(
                {
                    "run_id": run_id,
                    "persona_id": pid,
                    "question_id": question.id,
                    "paraphrase_idx": 0,
                    "response_value": {"response_value": int(value), "confidence": 0.85},
                }
            )

        # paraphrase_idx >= 1 — sub-swarm only
        for idx in range(1, n_paraphrases + 1):
            paraphrase_responses = _paraphrase_response_for(
                question, defect_class, is_affected, n_sub_swarm, rng,
                paraphrase_idx=idx,
            )
            for pid, value in zip(sub_swarm_ids, paraphrase_responses):
                rows.append(
                    {
                        "run_id": run_id,
                        "persona_id": pid,
                        "question_id": question.id,
                        "paraphrase_idx": idx,
                        "response_value": {"response_value": int(value), "confidence": 0.85},
                    }
                )

    if defect_class == "redundant_pair" and len(affected_question_ids) == 2:
        _make_correlated(rows, affected_question_ids, rng)

    return rows


def _baseline_response_for(
    question: Question,
    defect_class: DefectClass | None,
    is_affected: bool,
    n: int,
    rng: np.random.Generator,
    *,
    paraphrase_idx: int,
) -> np.ndarray:
    if not is_affected or defect_class is None:
        return _baseline_distribution(question, n, rng)

    if defect_class in ("leading_wording", "loaded_language"):
        # Original wording is heavily skewed up — that's the leading effect
        return _shifted_distribution(question, n, rng, shift=0.65)

    if defect_class == "double_barreled":
        return _diluted_distribution(question, n, rng)

    if defect_class == "fatigue_block":
        return _satisficing_distribution(question, n, rng)

    if defect_class == "redundant_pair":
        return _baseline_distribution(question, n, rng)

    return _baseline_distribution(question, n, rng)


def _paraphrase_response_for(
    question: Question,
    defect_class: DefectClass | None,
    is_affected: bool,
    n: int,
    rng: np.random.Generator,
    *,
    paraphrase_idx: int,
) -> np.ndarray:
    if not is_affected or defect_class is None:
        return _baseline_distribution(question, n, rng)

    if defect_class in ("leading_wording", "loaded_language"):
        # Neutralized paraphrases — back near baseline, demonstrating shift
        return _baseline_distribution(question, n, rng)

    if defect_class == "double_barreled":
        return _diluted_distribution(question, n, rng)

    if defect_class == "fatigue_block":
        return _satisficing_distribution(question, n, rng)

    return _baseline_distribution(question, n, rng)


def _make_correlated(
    rows: list[dict[str, Any]],
    pair: tuple[str, ...],
    rng: np.random.Generator,
    *,
    target_correlation: float = 0.92,
) -> None:
    """Post-process rows so two questions' baseline (paraphrase_idx=0) responses
    are highly correlated across personas."""
    a_id, b_id = pair[0], pair[1]
    by_persona_a: dict[str, dict[str, Any]] = {}
    by_persona_b: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row["question_id"] == a_id and row["paraphrase_idx"] == 0:
            by_persona_a[row["persona_id"]] = row
        elif row["question_id"] == b_id and row["paraphrase_idx"] == 0:
            by_persona_b[row["persona_id"]] = row

    common = sorted(set(by_persona_a) & set(by_persona_b))
    if not common:
        return

    a_values = np.array(
        [by_persona_a[p]["response_value"]["response_value"] for p in common],
        dtype=float,
    )
    noise = rng.normal(loc=0.0, scale=0.5, size=len(common))
    b_values = target_correlation * (a_values - a_values.mean()) + a_values.mean() + (
        np.sqrt(1 - target_correlation**2) * noise
    )
    b_values = np.clip(np.round(b_values), 1, 5).astype(int)

    for p, v in zip(common, b_values):
        by_persona_b[p]["response_value"]["response_value"] = int(v)
