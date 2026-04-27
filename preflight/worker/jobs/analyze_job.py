"""Analyze job — runs all statistical analyzers against the persisted response
matrix, composes the report card, persists it, and transitions the run to
completed.
"""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from preflight.db.models import Report, Run
from preflight.logging import get_logger
from preflight.schemas.run import JobPayload
from preflight.schemas.survey import Survey
from preflight.stats.analyzers import (
    correlation as correlation_analyzer,
    irt as irt_analyzer,
    paraphrase_shift,
    quota_montecarlo,
    screener_graph,
)
from preflight.stats.report_composer import compose
from preflight.worker.queue import JobQueue
from preflight.worker.state import set_run_status

logger = get_logger(__name__)


async def handle_analyze(
    payload: JobPayload,
    session: AsyncSession,
    queue: JobQueue,
) -> None:
    run = await session.get(Run, payload.run_id)
    if run is None:
        raise ValueError(f"run {payload.run_id} not found")

    survey = Survey.model_validate(run.survey_json)

    paraphrase_flags = []
    for question in survey.questions:
        flag = await paraphrase_shift.analyze_question(session, run.id, question)
        paraphrase_flags.append(flag)

    irt_flags = await irt_analyzer.analyze(session, run.id, survey)
    redundancy_flags = await correlation_analyzer.analyze(session, run.id, survey)
    screener_flags = screener_graph.analyze(survey)
    quota_flags = quota_montecarlo.analyze(survey)

    report = compose(
        run_id=run.id,
        survey=survey,
        paraphrase_flags=paraphrase_flags,
        irt_flags=irt_flags,
        redundancy_flags=redundancy_flags,
        screener_flags=screener_flags,
        quota_flags=quota_flags,
    )

    stmt = pg_insert(Report).values(
        run_id=run.id,
        report_json=report.model_dump(mode="json"),
        calibration_version="dev",
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["run_id"],
        set_={
            "report_json": stmt.excluded.report_json,
            "calibration_version": stmt.excluded.calibration_version,
        },
    )
    await session.execute(stmt)
    await session.commit()

    logger.info(
        "job.analyze.done",
        run_id=str(run.id),
        n_question_flags=len(paraphrase_flags),
        n_irt_flags=len(irt_flags),
        n_redundancy=len(redundancy_flags),
        n_screener=len(screener_flags),
        n_quota=len(quota_flags),
    )

    await set_run_status(session, run.id, "completed")
