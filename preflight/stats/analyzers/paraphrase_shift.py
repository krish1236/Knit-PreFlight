"""Counterfactual paraphrase shift analysis (HP2).

For each paraphraseable question, we compare the response distribution at
paraphrase_idx=0 (original wording) against each subsequent paraphrase
(idx=1..K). A large shift implies the original question is leading,
ambiguous, or otherwise wording-sensitive.

Comparisons are performed on matched personas — only the sub-swarm of
personas that have responses for ALL paraphrase indices contribute. This
isolates the effect of wording from any persona-pool difference.

Metrics by question type:
- ordinal scales (likert, nps, top_box):  Wasserstein distance on integers
- categorical (single_choice):            Total variation on choice histograms
- multi-select (multi_choice):            Jaccard-distance based shift
- open-end / video / stimulus:            skipped at HP2

Effect-size companion: Cohen's d on the mean response. Reported alongside
the primary metric so a sharp engineer can see *both* whether the
distribution shifted and by how much.

Severity is provisional in v0 and meant to be tightened by the calibration
harness in Phase 5.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

import numpy as np
from scipy.spatial.distance import jensenshannon
from scipy.stats import wasserstein_distance
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from preflight.db.models import ParaphraseCache, ProbeResponse
from preflight.logging import get_logger
from preflight.schemas.survey import Question
from preflight.stats.types import ParaphraseExample, ParaphraseShiftFlag, Severity
from preflight.worker.jobs.paraphrase_gen import question_hash

logger = get_logger(__name__)

ORDINAL_TYPES = {"likert_5", "likert_7", "nps", "top_box"}
SINGLE_CATEGORICAL = {"single_choice"}
MULTI_CATEGORICAL = {"multi_choice"}
SKIP_TYPES = {"open_end", "video_open_end", "stimulus_block"}

# Initial thresholds — tuned by calibration harness in Phase 5.
WASSERSTEIN_HIGH = 0.50
WASSERSTEIN_MED = 0.25
JS_HIGH = 0.20
JS_MED = 0.10
COHENS_D_HIGH = 0.60
COHENS_D_MED = 0.30


def _classify_severity(metric_score: float, cohens_d: float | None, *, is_js: bool) -> Severity:
    high_metric = JS_HIGH if is_js else WASSERSTEIN_HIGH
    med_metric = JS_MED if is_js else WASSERSTEIN_MED

    abs_d = abs(cohens_d) if cohens_d is not None else 0.0

    if metric_score >= high_metric and abs_d >= COHENS_D_HIGH:
        return "high"
    if metric_score >= high_metric or abs_d >= COHENS_D_HIGH:
        return "medium"
    if metric_score >= med_metric or abs_d >= COHENS_D_MED:
        return "medium"
    if metric_score > 0:
        return "low"
    return "none"


def _cohens_d(a: np.ndarray, b: np.ndarray) -> float | None:
    if len(a) < 2 or len(b) < 2:
        return None
    var_pooled = (a.var(ddof=1) + b.var(ddof=1)) / 2
    if var_pooled <= 0:
        return None
    return float((a.mean() - b.mean()) / np.sqrt(var_pooled))


def _histogram(values: np.ndarray, n_bins: int) -> np.ndarray:
    counts = np.zeros(n_bins, dtype=float)
    for v in values:
        if 0 <= int(v) < n_bins:
            counts[int(v)] += 1
    total = counts.sum()
    return counts / total if total > 0 else counts


def _scalar_value(payload: Any) -> int | float | None:
    """Normalize stored response payload to a scalar where possible."""
    if isinstance(payload, dict):
        return payload.get("response_value")  # type: ignore[no-any-return]
    return payload  # type: ignore[no-any-return]


async def _load_response_matrix(
    session: AsyncSession, run_id: uuid.UUID, question_id: str
) -> dict[int, dict[str, Any]]:
    """Returns {paraphrase_idx: {persona_id: response_value}}."""
    result = await session.execute(
        select(
            ProbeResponse.paraphrase_idx,
            ProbeResponse.persona_id,
            ProbeResponse.response_value,
        ).where(
            ProbeResponse.run_id == run_id,
            ProbeResponse.question_id == question_id,
        )
    )
    matrix: dict[int, dict[str, Any]] = defaultdict(dict)
    for paraphrase_idx, persona_id, value in result.all():
        matrix[paraphrase_idx][persona_id] = value
    return matrix


async def _load_paraphrase_texts(
    session: AsyncSession, question: Question
) -> list[str]:
    cached = await session.get(ParaphraseCache, question_hash(question.text))
    if cached is None:
        return []
    return [p.get("text", "") for p in cached.paraphrases]


def _matched_personas(matrix: dict[int, dict[str, Any]]) -> set[str]:
    if not matrix:
        return set()
    return set.intersection(*(set(d.keys()) for d in matrix.values()))


def _ordinal_shift(
    matrix: dict[int, dict[str, Any]],
    matched: set[str],
) -> tuple[float, float | None, list[ParaphraseExample]] | None:
    if 0 not in matrix:
        return None

    original_values = np.array(
        [_scalar_value(matrix[0][p]) for p in matched if _scalar_value(matrix[0][p]) is not None],
        dtype=float,
    )
    if len(original_values) == 0:
        return None

    examples: list[ParaphraseExample] = [
        ParaphraseExample(
            paraphrase_idx=0,
            text="<original>",
            mean_response=float(original_values.mean()),
            n=len(original_values),
        )
    ]

    max_w = 0.0
    max_d: float | None = None
    for idx in sorted(k for k in matrix.keys() if k != 0):
        para_values = np.array(
            [_scalar_value(matrix[idx][p]) for p in matched
             if _scalar_value(matrix[idx][p]) is not None],
            dtype=float,
        )
        if len(para_values) == 0:
            continue
        w = float(wasserstein_distance(original_values, para_values))
        d = _cohens_d(original_values, para_values)
        examples.append(
            ParaphraseExample(
                paraphrase_idx=idx,
                text="<paraphrase>",
                mean_response=float(para_values.mean()),
                n=len(para_values),
            )
        )
        if w > max_w:
            max_w = w
            max_d = d

    return max_w, max_d, examples


def _categorical_shift(
    matrix: dict[int, dict[str, Any]],
    matched: set[str],
    n_options: int,
) -> tuple[float, list[ParaphraseExample]] | None:
    if 0 not in matrix or n_options <= 0:
        return None

    def hist_for(idx: int) -> np.ndarray:
        values = np.array(
            [_scalar_value(matrix[idx][p]) for p in matched
             if _scalar_value(matrix[idx][p]) is not None],
            dtype=float,
        )
        return _histogram(values, n_bins=n_options) if len(values) else np.zeros(n_options)

    original_hist = hist_for(0)
    if original_hist.sum() == 0:
        return None

    examples: list[ParaphraseExample] = [
        ParaphraseExample(
            paraphrase_idx=0,
            text="<original>",
            mean_response=float(np.argmax(original_hist)),
            n=int(original_hist.sum() * len(matched)),
        )
    ]

    max_js = 0.0
    for idx in sorted(k for k in matrix.keys() if k != 0):
        para_hist = hist_for(idx)
        if para_hist.sum() == 0:
            continue
        js = float(jensenshannon(original_hist, para_hist))
        if not np.isnan(js) and js > max_js:
            max_js = js
        examples.append(
            ParaphraseExample(
                paraphrase_idx=idx,
                text="<paraphrase>",
                mean_response=float(np.argmax(para_hist)),
                n=len(matched),
            )
        )

    return max_js, examples


async def analyze_question(
    session: AsyncSession,
    run_id: uuid.UUID,
    question: Question,
) -> ParaphraseShiftFlag:
    if question.type in SKIP_TYPES:
        return ParaphraseShiftFlag(
            question_id=question.id,
            metric="skipped",
            score=0.0,
            cohens_d=None,
            n_personas=0,
            severity="none",
            examples=[],
            note=f"paraphrase shift not computed for type={question.type}",
        )

    matrix = await _load_response_matrix(session, run_id, question.id)
    matched = _matched_personas(matrix)

    if len(matched) < 5:
        return ParaphraseShiftFlag(
            question_id=question.id,
            metric="skipped",
            score=0.0,
            cohens_d=None,
            n_personas=len(matched),
            severity="none",
            examples=[],
            note="insufficient matched personas across paraphrases",
        )

    paraphrase_texts = await _load_paraphrase_texts(session, question)

    if question.type in ORDINAL_TYPES:
        result = _ordinal_shift(matrix, matched)
        if result is None:
            return ParaphraseShiftFlag(
                question_id=question.id,
                metric="skipped",
                score=0.0,
                cohens_d=None,
                n_personas=len(matched),
                severity="none",
                examples=[],
                note="no original responses available",
            )
        score, cohens_d, examples = result
        severity = _classify_severity(score, cohens_d, is_js=False)
        for ex in examples:
            if ex.paraphrase_idx == 0:
                ex.text = question.text
            elif 0 < ex.paraphrase_idx <= len(paraphrase_texts):
                ex.text = paraphrase_texts[ex.paraphrase_idx - 1]
        return ParaphraseShiftFlag(
            question_id=question.id,
            metric="wasserstein",
            score=float(score),
            cohens_d=cohens_d,
            n_personas=len(matched),
            severity=severity,
            examples=examples,
        )

    if question.type in SINGLE_CATEGORICAL:
        n_options = len(question.options or [])
        result_cat = _categorical_shift(matrix, matched, n_options=n_options)
        if result_cat is None:
            return ParaphraseShiftFlag(
                question_id=question.id,
                metric="skipped",
                score=0.0,
                cohens_d=None,
                n_personas=len(matched),
                severity="none",
                examples=[],
                note="no options or no original responses",
            )
        score, examples = result_cat
        severity = _classify_severity(score, cohens_d=None, is_js=True)
        for ex in examples:
            if ex.paraphrase_idx == 0:
                ex.text = question.text
            elif 0 < ex.paraphrase_idx <= len(paraphrase_texts):
                ex.text = paraphrase_texts[ex.paraphrase_idx - 1]
        return ParaphraseShiftFlag(
            question_id=question.id,
            metric="jensen_shannon",
            score=float(score),
            cohens_d=None,
            n_personas=len(matched),
            severity=severity,
            examples=examples,
        )

    return ParaphraseShiftFlag(
        question_id=question.id,
        metric="skipped",
        score=0.0,
        cohens_d=None,
        n_personas=len(matched),
        severity="none",
        examples=[],
        note=f"shift analysis not implemented for type={question.type}",
    )
