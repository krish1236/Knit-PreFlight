"""IRT 2PL discrimination per question (HP4).

Architecture-doc framing applies: this is a *relative-within-survey* signal,
not an absolute psychometric score. We fit on synthetic responses, so the
extracted latent trait reflects the LLM's beliefs about persona-question
relationships, not real human latent traits.

Implementation: a compact joint-MLE 2PL fit via scipy.optimize. Avoids the
heavy Pyro/py-irt dependency. The 2PL log-likelihood for binary responses:

    P(y_ij = 1 | theta_i, a_j, b_j) = sigmoid(a_j * (theta_i - b_j))

Likert and other ordinal items are dichotomized at the median per question
before fitting (a documented v0 simplification). The discrimination
parameter `a` is what we surface; difficulty `b` is computed but not
directly reported.

Convergence-fragile: synthetic responses are sometimes degenerate (e.g.,
all 1000 personas answer identically). On convergence failure, we fall
back to a variance-based proxy and tag the flag as "experimental".
"""

from __future__ import annotations

import uuid
from collections import defaultdict

import numpy as np
from scipy.optimize import minimize
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from preflight.db.models import ProbeResponse
from preflight.logging import get_logger
from preflight.schemas.survey import Question, Survey
from preflight.stats.types import IRTFlag, Severity

logger = get_logger(__name__)

ORDINAL_TYPES = {"likert_5", "likert_7", "nps", "top_box"}

A_POOR_THRESHOLD = 0.5
A_STRONG_THRESHOLD = 1.0
PROXY_LOW_VARIANCE = 0.05


def _classify_severity(a: float) -> Severity:
    if a < A_POOR_THRESHOLD:
        return "high"
    if a < A_STRONG_THRESHOLD:
        return "medium"
    return "none"


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


def _neg_log_likelihood_2pl(
    params: np.ndarray, response_matrix: np.ndarray, n_persons: int, n_items: int
) -> float:
    """params layout: [theta_1..theta_n, a_1..a_m, b_1..b_m]."""
    theta = params[:n_persons]
    a = params[n_persons : n_persons + n_items]
    b = params[n_persons + n_items :]

    p = _sigmoid(a[None, :] * (theta[:, None] - b[None, :]))
    p = np.clip(p, 1e-9, 1 - 1e-9)
    mask = ~np.isnan(response_matrix)
    ll = np.where(
        mask,
        response_matrix * np.log(p) + (1 - response_matrix) * np.log(1 - p),
        0.0,
    )
    return -float(ll.sum())


def _fit_2pl(response_matrix: np.ndarray) -> tuple[np.ndarray, bool]:
    """Joint MLE via L-BFGS-B with mild ridge regularization to keep params bounded."""
    n_persons, n_items = response_matrix.shape

    rng = np.random.default_rng(42)
    theta_init = rng.normal(scale=0.3, size=n_persons)
    a_init = np.ones(n_items) * 0.8
    b_init = np.zeros(n_items)
    x0 = np.concatenate([theta_init, a_init, b_init])

    def objective(p: np.ndarray) -> float:
        nll = _neg_log_likelihood_2pl(p, response_matrix, n_persons, n_items)
        ridge = 1e-3 * float(np.sum(p[:n_persons] ** 2))
        return nll + ridge

    bounds = (
        [(-5.0, 5.0)] * n_persons
        + [(0.05, 4.0)] * n_items
        + [(-5.0, 5.0)] * n_items
    )

    try:
        result = minimize(
            objective,
            x0,
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": 200, "ftol": 1e-6},
        )
        return result.x, bool(result.success)
    except Exception as exc:
        logger.warning("irt.fit_failed", error=str(exc))
        return x0, False


async def _load_baseline_response_matrix(
    session: AsyncSession,
    run_id: uuid.UUID,
    questions: list[Question],
) -> tuple[np.ndarray, list[Question], list[str]]:
    """Build (n_persons, n_items) binary matrix from paraphrase_idx=0 responses."""
    eligible_questions = [q for q in questions if q.type in ORDINAL_TYPES]
    if not eligible_questions:
        return np.empty((0, 0)), [], []

    item_ids = [q.id for q in eligible_questions]
    result = await session.execute(
        select(
            ProbeResponse.persona_id,
            ProbeResponse.question_id,
            ProbeResponse.response_value,
        ).where(
            ProbeResponse.run_id == run_id,
            ProbeResponse.question_id.in_(item_ids),
            ProbeResponse.paraphrase_idx == 0,
        )
    )

    by_persona: dict[str, dict[str, float]] = defaultdict(dict)
    raw_per_question: dict[str, list[float]] = defaultdict(list)
    for persona_id, question_id, payload in result.all():
        scalar = payload.get("response_value") if isinstance(payload, dict) else payload
        if scalar is None:
            continue
        try:
            value = float(scalar)
        except (TypeError, ValueError):
            continue
        by_persona[persona_id][question_id] = value
        raw_per_question[question_id].append(value)

    persona_ids = sorted(by_persona.keys())
    medians: dict[str, float] = {
        qid: float(np.median(vals)) if vals else 0.0
        for qid, vals in raw_per_question.items()
    }

    matrix = np.full((len(persona_ids), len(eligible_questions)), np.nan, dtype=float)
    for i, pid in enumerate(persona_ids):
        for j, q in enumerate(eligible_questions):
            value = by_persona[pid].get(q.id)
            if value is not None:
                matrix[i, j] = 1.0 if value > medians[q.id] else 0.0

    return matrix, eligible_questions, persona_ids


def _variance_proxy(values: np.ndarray) -> float:
    if len(values) < 2:
        return 0.0
    return float(values[~np.isnan(values)].var(ddof=1))


async def analyze(
    session: AsyncSession,
    run_id: uuid.UUID,
    survey: Survey,
) -> list[IRTFlag]:
    matrix, items, persona_ids = await _load_baseline_response_matrix(
        session, run_id, survey.questions
    )

    if matrix.size == 0 or matrix.shape[0] < 30 or matrix.shape[1] < 2:
        logger.info("irt.skipped", reason="insufficient data", shape=matrix.shape)
        return []

    fitted, converged = _fit_2pl(matrix)
    n_persons, n_items = matrix.shape
    a_values = fitted[n_persons : n_persons + n_items]

    flags: list[IRTFlag] = []
    for j, question in enumerate(items):
        a = float(a_values[j])

        if not converged:
            proxy = _variance_proxy(matrix[:, j])
            severity: Severity = "high" if proxy < PROXY_LOW_VARIANCE else "none"
            if severity == "high":
                summary = (
                    "Responses were nearly identical across the persona pool, "
                    "so this question barely separates anyone — it likely won't "
                    "differentiate audience segments."
                )
            else:
                summary = (
                    "IRT 2PL did not converge on this synthetic data; using a "
                    "variance proxy as a sanity check. Treat as informational only."
                )
            flags.append(
                IRTFlag(
                    question_id=question.id,
                    discrimination=proxy,
                    interpretation="experimental",
                    convergence_ok=False,
                    n_personas=int((~np.isnan(matrix[:, j])).sum()),
                    severity=severity,
                    note="2PL did not converge; falling back to variance proxy",
                    summary=summary,
                )
            )
            continue

        if a < A_POOR_THRESHOLD:
            interp: str = "poor"
            summary = (
                f"Discrimination a={a:.2f} (poor). This question barely separates "
                f"personas at different latent-trait levels — it likely won't "
                f"differentiate audience segments. Consider redesigning."
            )
        elif a < A_STRONG_THRESHOLD:
            interp = "moderate"
            summary = (
                f"Discrimination a={a:.2f} (moderate). The question works but "
                f"isn't a strong segmenter."
            )
        else:
            interp = "strong"
            summary = (
                f"Discrimination a={a:.2f} (strong). Useful question for "
                f"separating audience segments."
            )

        flags.append(
            IRTFlag(
                question_id=question.id,
                discrimination=a,
                interpretation=interp,  # type: ignore[arg-type]
                convergence_ok=True,
                n_personas=int((~np.isnan(matrix[:, j])).sum()),
                severity=_classify_severity(a),
                summary=summary,
            )
        )

    logger.info(
        "irt.fit_complete",
        run_id=str(run_id),
        n_items=n_items,
        n_persons=n_persons,
        converged=converged,
    )
    return flags
