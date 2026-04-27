"""Report composer assembles analyzer outputs into a final ReportCard."""

from __future__ import annotations

import uuid

from preflight.schemas.survey import Question, Survey
from preflight.stats.report_composer import compose
from preflight.stats.types import (
    IRTFlag,
    ParaphraseShiftFlag,
    QuotaFeasibility,
    RedundancyFlag,
    ScreenerFlag,
)


def _survey() -> Survey:
    return Survey.model_validate(
        {
            "id": "compose-test",
            "version": "0.1",
            "brief": {"objectives": ["x"], "audience_criteria": "x"},
            "audience": {"age_range": {"min": 25, "max": 54}},
            "questions": [
                {"id": "Q1", "type": "likert_5", "text": "How satisfied?"},
                {"id": "Q2", "type": "likert_5", "text": "How likely to recommend?"},
            ],
        }
    )


def test_composer_combines_per_question_flags() -> None:
    run_id = uuid.uuid4()
    survey = _survey()
    paraphrase = [
        ParaphraseShiftFlag(
            question_id="Q1",
            metric="wasserstein",
            score=0.8,
            cohens_d=0.7,
            n_personas=200,
            severity="high",
            examples=[],
        ),
        ParaphraseShiftFlag(
            question_id="Q2",
            metric="wasserstein",
            score=0.05,
            cohens_d=0.1,
            n_personas=200,
            severity="none",
            examples=[],
        ),
    ]
    irt = [
        IRTFlag(
            question_id="Q1",
            discrimination=0.3,
            interpretation="poor",
            convergence_ok=True,
            n_personas=1000,
            severity="high",
        )
    ]

    report = compose(
        run_id=run_id,
        survey=survey,
        paraphrase_flags=paraphrase,
        irt_flags=irt,
        redundancy_flags=[],
        screener_flags=[],
        quota_flags=[],
    )

    assert report.run_id == run_id
    assert report.survey_id == "compose-test"
    assert len(report.per_question) == 2
    q1 = next(q for q in report.per_question if q.question_id == "Q1")
    assert q1.severity == "high"
    assert q1.paraphrase_shift is not None
    assert q1.irt is not None
    q2 = next(q for q in report.per_question if q.question_id == "Q2")
    assert q2.severity == "none"
    assert q2.irt is None
    assert report.estimated_panel_exposure.high_severity_questions == 1
    assert report.estimated_panel_exposure.flagged_question_count == 1


def test_composer_takes_max_severity() -> None:
    run_id = uuid.uuid4()
    survey = _survey()
    paraphrase = [
        ParaphraseShiftFlag(
            question_id="Q1",
            metric="wasserstein",
            score=0.05,
            cohens_d=0.1,
            n_personas=200,
            severity="low",
            examples=[],
        )
    ]
    irt = [
        IRTFlag(
            question_id="Q1",
            discrimination=0.2,
            interpretation="poor",
            convergence_ok=True,
            n_personas=1000,
            severity="high",
        )
    ]

    report = compose(
        run_id=run_id,
        survey=survey,
        paraphrase_flags=paraphrase,
        irt_flags=irt,
        redundancy_flags=[],
        screener_flags=[],
        quota_flags=[],
    )
    q1 = next(q for q in report.per_question if q.question_id == "Q1")
    assert q1.severity == "high"


def test_composer_passes_through_aggregate_lists() -> None:
    run_id = uuid.uuid4()
    survey = _survey()
    redundancy = [
        RedundancyFlag(
            q_id_a="Q1",
            q_id_b="Q2",
            pearson=0.92,
            spearman=0.91,
            n_personas=200,
            severity="high",
        )
    ]
    screener = [
        ScreenerFlag(
            type="self_loop",
            description="Q1 references itself",
            severity="high",
        )
    ]
    quota = [
        QuotaFeasibility(
            cell={"age_bucket": "25-34"},
            target_n=200,
            estimated_panel_pct=0.4,
            estimated_n_at_target=1,
            severity="high",
        )
    ]

    report = compose(
        run_id=run_id,
        survey=survey,
        paraphrase_flags=[],
        irt_flags=[],
        redundancy_flags=redundancy,
        screener_flags=screener,
        quota_flags=quota,
    )

    assert len(report.redundancy_pairs) == 1
    assert len(report.screener_issues) == 1
    assert len(report.quota_feasibility) == 1
    assert "probes used for instrument" in report.framing_disclaimer.lower()
