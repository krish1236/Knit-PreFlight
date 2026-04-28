"""Pre-compute report cards for seeded sample surveys so the demo UI's
60-second test path returns instant results.

Reuses the calibration synthesizer (no LLM, deterministic). For samples that
were authored with deliberate defects, we mark the affected questions and
synthesize responses that carry the appropriate signature so the analyzers
fire as designed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from preflight.calibration.injection.types import DefectClass
from preflight.calibration.synthesis import synthesize_response_matrix
from preflight.db.models import ParaphraseCache, ProbeResponse, Report, Run
from preflight.logging import get_logger
from preflight.schemas.survey import Survey
from preflight.seeds.sample_loader import load_sample_files
from preflight.stats.analyzers import (
    correlation as correlation_analyzer,
    irt as irt_analyzer,
    paraphrase_shift,
    quota_montecarlo,
    screener_graph,
)
from preflight.stats.report_composer import compose
from preflight.worker.jobs.paraphrase_gen import question_hash

logger = get_logger(__name__)


@dataclass(frozen=True)
class SampleAnnotation:
    """Which questions in a sample carry which planted defect, plus the canned
    neutral paraphrases that the precompute path writes into paraphrase_cache so
    the report-card UI shows real wording instead of '<paraphrase>' placeholders.
    """

    affected_question_ids: tuple[str, ...]
    defect_class: DefectClass | None
    paraphrases_by_qid: dict[str, list[str]]


# Hand-authored neutral paraphrases for each question in the sample surveys.
# These are what the demo UI shows in the "Wording variants × mean response"
# panel. The precompute path writes them into paraphrase_cache before running
# analyzers so the user sees a real before/after comparison.
ANNOTATIONS: dict[str, SampleAnnotation] = {
    "sample-01-clean": SampleAnnotation(
        affected_question_ids=(),
        defect_class=None,
        paraphrases_by_qid={
            "Q1": [
                "How would you rate your overall satisfaction with your current mobile carrier?",
                "Rate your level of satisfaction with your current mobile carrier.",
                "Please indicate how satisfied you are with your current mobile carrier.",
                "On a scale, where do you stand on satisfaction with your current mobile carrier?",
                "Considering everything, how satisfied would you say you are with your current carrier?",
            ],
            "Q2": [
                "How would you rate your current plan's value for the money?",
                "Please rate the value-for-money of your current mobile plan.",
                "How does the value of your current plan compare to what you pay?",
                "Considering price and benefits, how would you rate your plan's value?",
                "On the value-for-money dimension, how do you rate your current plan?",
            ],
            "Q3": [
                "How likely would you be to recommend your carrier to a friend or colleague?",
                "Would you recommend your current carrier to a friend or colleague?",
                "What is the likelihood you would recommend your carrier to others?",
                "Rate the likelihood that you would recommend your carrier.",
                "How willing are you to recommend your current carrier to others?",
            ],
            "Q4": [
                "Of these, which factor matters most to you when choosing a mobile carrier?",
                "When picking a carrier, which of these factors is most important?",
                "Which factor is the top consideration when you choose a mobile carrier?",
                "Among these options, which matters most in your carrier choice?",
                "Which of the following weighs heaviest in your carrier decision?",
            ],
            "Q5": [
                "How would you rate the network coverage your carrier provides in your area?",
                "Rate the quality of your carrier's network coverage where you live.",
                "What is your assessment of network coverage from your carrier?",
                "How well does your carrier's network cover your area?",
                "Please rate your carrier's coverage in the area you live.",
            ],
        },
    ),
    "sample-02-defects": SampleAnnotation(
        affected_question_ids=("Q1", "Q6", "Q7"),
        defect_class="leading_wording",
        paraphrases_by_qid={
            "Q1": [
                "How important is bold packaging when choosing an energy drink?",
                "When picking an energy drink, how much does packaging design matter?",
                "Rate the importance of bold packaging in your energy drink choice.",
                "How does packaging weigh in on your energy drink decision?",
                "What role does packaging play when you choose an energy drink?",
            ],
            "Q2": [
                "How appealing do you find this concept?",
                "Rate the appeal of this concept.",
                "How attractive is this concept to you?",
                "What is your level of appeal toward this concept?",
                "How would you rate this concept's appeal?",
            ],
            "Q3": [
                "Rate how appealing this energy drink concept is.",
                "How attractive does this energy drink concept seem to you?",
                "On the appeal dimension, where does this concept land?",
                "How would you score the appeal of this energy drink concept?",
                "What is your reaction to the appeal of this concept?",
            ],
            "Q4": [
                "How would you rate this energy drink design?",
                "Rate this energy drink's design.",
                "How does this design strike you?",
                "What is your assessment of this design?",
                "Please rate the design of this energy drink.",
            ],
            "Q5": [
                "Of these, which is the most important reason to switch energy drinks?",
                "Which of these factors most often drives a switch in energy drinks?",
                "What is the leading reason among these to change energy drinks?",
                "Which factor would most influence your switch to a new energy drink?",
                "Among these, which carries the most weight in switching brands?",
            ],
            "Q6": [
                "How important is it that an energy drink tastes great and is affordable?",
                "Rate the importance of taste and affordability in an energy drink.",
                "How much do taste and price matter in an energy drink?",
                "Considering taste and price, how important are they to you?",
                "What weight do taste and affordability carry for you in this category?",
            ],
            "Q7": [
                "How would you rate this energy drink?",
                "What is your reaction to this energy drink?",
                "Rate this energy drink on overall liking.",
                "Where does this energy drink land on your overall opinion?",
                "How would you assess this energy drink overall?",
            ],
        },
    ),
    "sample-03-mixed": SampleAnnotation(
        affected_question_ids=("Q4",),
        defect_class="leading_wording",
        paraphrases_by_qid={
            "Q1": [
                "What is your level of familiarity with 'Pacific Pure'?",
                "Rate your familiarity with the 'Pacific Pure' brand.",
                "How well do you know the brand 'Pacific Pure'?",
                "How recognizable is 'Pacific Pure' to you?",
                "How aware are you of the 'Pacific Pure' brand?",
            ],
            "Q2": [
                "What is your overall view of 'Pacific Pure'?",
                "How would you describe your view of the 'Pacific Pure' brand?",
                "Rate your overall opinion of 'Pacific Pure'.",
                "How positively or negatively do you view the brand?",
                "Where does 'Pacific Pure' land on your view of brands?",
            ],
            "Q3": [
                "How much trust do you place in 'Pacific Pure' as a brand?",
                "Rate your level of trust in 'Pacific Pure'.",
                "How confident are you in 'Pacific Pure' as a brand?",
                "What level of trust does 'Pacific Pure' have with you?",
                "On a trust dimension, where does 'Pacific Pure' sit?",
            ],
            "Q4": [
                "How does 'Pacific Pure's' value compare to similar brands?",
                "Compared to similar brands, how would you rate 'Pacific Pure's' value?",
                "On the value dimension, how does 'Pacific Pure' stack up against similar brands?",
                "Rate the value of 'Pacific Pure' relative to comparable brands.",
                "How does 'Pacific Pure' compare with similar brands on value?",
            ],
            "Q5": [
                "How likely are you to recommend 'Pacific Pure' to others?",
                "What is the likelihood you would recommend 'Pacific Pure'?",
                "Would you recommend 'Pacific Pure' to friends or family?",
                "Rate the likelihood that you would recommend 'Pacific Pure'.",
                "How willing are you to recommend 'Pacific Pure' to others?",
            ],
            "Q6": [
                "How would you characterize your history with 'Pacific Pure'?",
                "What is your buying relationship with 'Pacific Pure'?",
                "Of these, which describes your purchase pattern with 'Pacific Pure'?",
                "Which of the following matches your experience with 'Pacific Pure'?",
                "Which option best fits your purchase history with 'Pacific Pure'?",
            ],
            "Q7": [
                "How aware have you been of 'Pacific Pure' advertising in the past 30 days?",
                "Rate how often you've seen 'Pacific Pure' advertising recently.",
                "What level of 'Pacific Pure' advertising have you noticed in the past month?",
                "How prominent has 'Pacific Pure' advertising been to you lately?",
                "Have you noticed 'Pacific Pure' advertising in the past 30 days?",
            ],
            "Q8": [
                "Rate the memorability of the 'Pacific Pure' advertising.",
                "How well do you remember the 'Pacific Pure' advertising?",
                "Did the 'Pacific Pure' advertising stick with you?",
                "On a memorability scale, where does the advertising sit?",
                "How vividly do you recall the 'Pacific Pure' advertising?",
            ],
        },
    ),
}


async def _populate_paraphrase_cache(session: AsyncSession, survey: Survey) -> None:
    """Insert hand-authored paraphrases into paraphrase_cache so analyzers and
    the report-card UI surface real wording rather than placeholder text.
    """
    annotation = ANNOTATIONS.get(survey.id)
    if annotation is None:
        return

    from sqlalchemy.dialects.postgresql import insert as pg_insert

    for question in survey.questions:
        texts = annotation.paraphrases_by_qid.get(question.id)
        if not texts:
            continue
        payload = [
            {"text": t, "axis": f"neutral_{i}", "validated": True}
            for i, t in enumerate(texts)
        ]
        stmt = pg_insert(ParaphraseCache).values(
            question_hash=question_hash(question.text),
            paraphrases=payload,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["question_hash"],
            set_={"paraphrases": stmt.excluded.paraphrases},
        )
        await session.execute(stmt)
    await session.commit()


async def precompute_for_run(
    session: AsyncSession,
    run: Run,
    *,
    n_baseline: int = 600,
    n_sub_swarm: int = 150,
    seed: int = 42,
) -> uuid.UUID:
    """Synthesize responses for the run's survey, run analyzers, persist report.
    Idempotent: deletes any prior probe_responses + report for this run first.
    """
    survey = Survey.model_validate(run.survey_json)
    annotation = ANNOTATIONS.get(
        survey.id,
        SampleAnnotation(affected_question_ids=(), defect_class=None, paraphrases_by_qid={}),
    )

    await session.execute(delete(ProbeResponse).where(ProbeResponse.run_id == run.id))
    await session.execute(delete(Report).where(Report.run_id == run.id))
    await session.commit()

    await _populate_paraphrase_cache(session, survey)

    rows = synthesize_response_matrix(
        run_id=run.id,
        survey=survey,
        affected_question_ids=annotation.affected_question_ids,
        defect_class=annotation.defect_class,
        n_baseline_personas=n_baseline,
        n_sub_swarm=n_sub_swarm,
        seed=seed,
    )
    await session.execute(pg_insert(ProbeResponse), rows)
    await session.commit()

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
        calibration_version="precomputed",
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["run_id"],
        set_={
            "report_json": stmt.excluded.report_json,
            "calibration_version": stmt.excluded.calibration_version,
        },
    )
    await session.execute(stmt)

    run.status = "completed"
    from datetime import UTC, datetime

    run.completed_at = datetime.now(UTC)
    await session.commit()

    logger.info(
        "samples.precomputed",
        survey_id=survey.id,
        run_id=str(run.id),
        defect_class=annotation.defect_class,
        affected=annotation.affected_question_ids,
    )
    return run.id


async def precompute_all_samples(session: AsyncSession) -> list[uuid.UUID]:
    """For each seeded sample run, synthesize responses and persist a completed report."""
    out: list[uuid.UUID] = []
    for slug, survey_dict in load_sample_files():
        survey_id = survey_dict["id"]
        result = await session.execute(
            select(Run).where(Run.survey_id == survey_id, Run.is_sample.is_(True))
        )
        run = result.scalar_one_or_none()
        if run is None:
            logger.warning("samples.no_seeded_run", slug=slug, survey_id=survey_id)
            continue
        out.append(await precompute_for_run(session, run))
    return out
