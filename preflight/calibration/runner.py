"""Calibration runner.

Generates a clean corpus, injects every (defect_class, severity) into every
clean survey, synthesizes a probe-response matrix per variant, and runs
every analyzer against it. Tallies precision / recall / F1 by defect class
and severity, then persists a CalibrationRun row.

This is the offline counterpart to the live `analyze` job — same analyzers,
synthetic responses instead of real Sonnet calls.
"""

from __future__ import annotations

import os
import subprocess
import uuid
from dataclasses import dataclass

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from preflight.calibration.corpus.seed_surveys import generate_clean_corpus
from preflight.calibration.injection.registry import all_classes, inject
from preflight.calibration.injection.types import (
    ALL_SEVERITIES,
    DefectClass,
    Severity,
)
from preflight.calibration.metrics import CalibrationResults
from preflight.calibration.synthesis import synthesize_response_matrix
from preflight.db.models import (
    CalibrationRun,
    ProbeResponse,
    Run,
)
from preflight.logging import get_logger
from preflight.persona.pool_generator import audience_hash
from preflight.persona.schema import ResponseStyleConfig
from preflight.schemas.report import ReportCard
from preflight.schemas.survey import Survey
from preflight.stats.analyzers import (
    correlation as correlation_analyzer,
    irt as irt_analyzer,
    paraphrase_shift,
    quota_montecarlo,
    screener_graph,
)
from preflight.stats.report_composer import compose

logger = get_logger(__name__)


# Map of (analyzer-output-flag) -> defect class. Used to translate ReportCard
# entries back into the defect-class space for F1 scoring.
def _detected_classes(report: ReportCard) -> list[DefectClass]:
    detected: list[DefectClass] = []

    for q in report.per_question:
        if q.severity in ("medium", "high"):
            if (
                q.paraphrase_shift
                and q.paraphrase_shift.severity in ("medium", "high")
            ):
                # paraphrase shift fires on leading_wording or loaded_language
                detected.append("leading_wording")
            if q.irt and q.irt.severity in ("medium", "high"):
                # low IRT discrimination signals double_barreled or fatigue_block
                detected.append("double_barreled")

    if any(r.severity in ("medium", "high") for r in report.redundancy_pairs):
        detected.append("redundancy_pair" if False else "redundant_pair")

    if any(s.severity == "high" for s in report.screener_issues):
        detected.append("infeasible_screener")

    if any(q.severity in ("medium", "high") for q in report.quota_feasibility):
        detected.append("infeasible_screener")

    return detected


@dataclass
class CalibrationConfig:
    n_clean_surveys: int = 12
    n_baseline_personas: int = 200
    n_sub_swarm: int = 60
    n_paraphrases: int = 5
    seed: int = 7


async def _persist_synthetic(
    session: AsyncSession,
    survey: Survey,
    affected: tuple[str, ...],
    defect_class: DefectClass | None,
    cfg: CalibrationConfig,
    seed: int,
) -> tuple[uuid.UUID, ReportCard]:
    """Insert a transient run + synthetic responses, run analyzers, return
    composed report. Caller is responsible for cleanup."""
    run_id = uuid.uuid4()
    h = audience_hash(survey.audience, ResponseStyleConfig(), n=cfg.n_baseline_personas, seed=seed)
    run = Run(
        id=run_id,
        survey_id=survey.id,
        survey_json=survey.model_dump(mode="json"),
        status="stats_running",
        audience_hash=h,
        is_sample=False,
    )
    session.add(run)
    await session.flush()

    rows = synthesize_response_matrix(
        run_id=run_id,
        survey=survey,
        affected_question_ids=affected,
        defect_class=defect_class,
        n_baseline_personas=cfg.n_baseline_personas,
        n_sub_swarm=cfg.n_sub_swarm,
        n_paraphrases=cfg.n_paraphrases,
        seed=seed,
    )
    await session.execute(pg_insert(ProbeResponse), rows)
    await session.commit()

    paraphrase_flags = []
    for question in survey.questions:
        flag = await paraphrase_shift.analyze_question(session, run_id, question)
        paraphrase_flags.append(flag)

    irt_flags = await irt_analyzer.analyze(session, run_id, survey)
    redundancy_flags = await correlation_analyzer.analyze(session, run_id, survey)
    screener_flags = screener_graph.analyze(survey)
    quota_flags = quota_montecarlo.analyze(survey)

    report = compose(
        run_id=run_id,
        survey=survey,
        paraphrase_flags=paraphrase_flags,
        irt_flags=irt_flags,
        redundancy_flags=redundancy_flags,
        screener_flags=screener_flags,
        quota_flags=quota_flags,
    )

    await session.execute(delete(ProbeResponse).where(ProbeResponse.run_id == run_id))
    await session.execute(delete(Run).where(Run.id == run_id))
    await session.commit()

    return run_id, report


async def run_calibration(
    session: AsyncSession,
    config: CalibrationConfig | None = None,
    *,
    persist: bool = True,
) -> CalibrationResults:
    cfg = config or CalibrationConfig()
    results = CalibrationResults()

    clean_corpus = generate_clean_corpus(n=cfg.n_clean_surveys, seed=cfg.seed)
    n_total = len(clean_corpus) * (1 + len(all_classes()) * len(ALL_SEVERITIES))
    logger.info("calibration.start", n_iterations=n_total, n_clean=len(clean_corpus))

    iteration = 0

    for clean in clean_corpus:
        iteration += 1
        _, report = await _persist_synthetic(
            session, clean, affected=(), defect_class=None,
            cfg=cfg, seed=cfg.seed + iteration,
        )
        observed = _detected_classes(report)
        results.record(expected=None, severity=None, observed=observed)

        for defect_class in all_classes():
            for severity in ALL_SEVERITIES:
                iteration += 1
                injected = inject(clean, defect_class, severity, seed=cfg.seed + iteration)
                _, report = await _persist_synthetic(
                    session,
                    injected.survey,
                    affected=injected.affected_question_ids,
                    defect_class=defect_class,
                    cfg=cfg,
                    seed=cfg.seed + iteration,
                )
                observed = _detected_classes(report)
                results.record(
                    expected=defect_class, severity=severity, observed=observed
                )

    if persist:
        sha = _git_sha()
        cal_run = CalibrationRun(
            id=uuid.uuid4(),
            git_sha=sha,
            f1_overall=results.overall_macro_f1(),
            f1_per_class={
                cls: agg.f1 for cls, agg in results.per_class_aggregate().items()
            },
            n_surveys=cfg.n_clean_surveys,
        )
        session.add(cal_run)
        await session.commit()
        logger.info(
            "calibration.persisted",
            git_sha=sha,
            f1=results.overall_macro_f1(),
            n_surveys=cfg.n_clean_surveys,
        )

    return results


def _git_sha() -> str:
    sha = os.environ.get("GIT_SHA")
    if sha:
        return sha[:40]
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, timeout=2
        ).decode().strip()[:40]
    except Exception:
        return "local"
