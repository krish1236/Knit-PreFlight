"""Inter-question redundancy detection via response correlation.

Pairs of questions whose responses move together across the persona pool
are functionally redundant — they extract the same signal and waste
respondent time. We compute Pearson and Spearman rank correlation across
the baseline (paraphrase_idx=0) responses; pairs above the threshold are
flagged.
"""

from __future__ import annotations

import uuid
from collections import defaultdict

import numpy as np
from scipy.stats import pearsonr, spearmanr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from preflight.db.models import ProbeResponse
from preflight.logging import get_logger
from preflight.schemas.survey import Question, Survey
from preflight.stats.types import RedundancyFlag, Severity

logger = get_logger(__name__)

ORDINAL_TYPES = {"likert_5", "likert_7", "nps", "top_box"}

PEARSON_HIGH = 0.85
PEARSON_MED = 0.70
MIN_PAIRWISE_PERSONAS = 20


def _classify(pearson: float) -> Severity:
    if abs(pearson) >= PEARSON_HIGH:
        return "high"
    if abs(pearson) >= PEARSON_MED:
        return "medium"
    return "none"


async def _load_per_persona_per_question(
    session: AsyncSession, run_id: uuid.UUID, question_ids: list[str]
) -> dict[str, dict[str, float]]:
    """Returns {persona_id: {question_id: scalar_response}} for paraphrase_idx=0."""
    result = await session.execute(
        select(
            ProbeResponse.persona_id,
            ProbeResponse.question_id,
            ProbeResponse.response_value,
        ).where(
            ProbeResponse.run_id == run_id,
            ProbeResponse.paraphrase_idx == 0,
            ProbeResponse.question_id.in_(question_ids),
        )
    )
    out: dict[str, dict[str, float]] = defaultdict(dict)
    for persona_id, question_id, payload in result.all():
        scalar = payload.get("response_value") if isinstance(payload, dict) else payload
        if scalar is None:
            continue
        try:
            out[persona_id][question_id] = float(scalar)
        except (TypeError, ValueError):
            continue
    return out


async def analyze(
    session: AsyncSession,
    run_id: uuid.UUID,
    survey: Survey,
) -> list[RedundancyFlag]:
    eligible = [q for q in survey.questions if q.type in ORDINAL_TYPES]
    if len(eligible) < 2:
        return []

    qids = [q.id for q in eligible]
    rows = await _load_per_persona_per_question(session, run_id, qids)

    flags: list[RedundancyFlag] = []
    for i in range(len(eligible)):
        for j in range(i + 1, len(eligible)):
            qi, qj = eligible[i], eligible[j]
            paired = [
                (vals[qi.id], vals[qj.id])
                for vals in rows.values()
                if qi.id in vals and qj.id in vals
            ]
            if len(paired) < MIN_PAIRWISE_PERSONAS:
                continue

            a = np.array([p[0] for p in paired], dtype=float)
            b = np.array([p[1] for p in paired], dtype=float)
            if a.std() == 0 or b.std() == 0:
                continue

            pearson_r = float(pearsonr(a, b).statistic)
            spearman_r = float(spearmanr(a, b).statistic)
            if np.isnan(pearson_r) or np.isnan(spearman_r):
                continue

            severity = _classify(pearson_r)
            if severity == "none":
                continue

            direction = "the same" if pearson_r > 0 else "opposite"
            if severity == "high":
                verdict = (
                    f"{qi.id} and {qj.id} effectively measure {direction} thing "
                    f"(correlation {pearson_r:+.2f}). Drop one to save respondent "
                    f"time and avoid double-counting in analysis."
                )
            else:
                verdict = (
                    f"{qi.id} and {qj.id} are correlated {pearson_r:+.2f}. "
                    f"Consider whether both add unique signal."
                )
            flags.append(
                RedundancyFlag(
                    q_id_a=qi.id,
                    q_id_b=qj.id,
                    pearson=pearson_r,
                    spearman=spearman_r,
                    n_personas=len(paired),
                    severity=severity,
                    summary=verdict,
                )
            )

    logger.info(
        "redundancy.complete",
        run_id=str(run_id),
        n_eligible=len(eligible),
        n_flags=len(flags),
    )
    return flags
