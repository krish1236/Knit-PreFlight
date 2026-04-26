"""Probe-response job: per-question collection of (persona × paraphrase) Sonnet calls.

Reuses the persona system prompt across all calls within a question for prompt-cache
benefit. Persists structured responses to probe_responses keyed by
(run_id, persona_id, question_id, paraphrase_idx). Idempotent — the upsert means
re-runs of the same job converge.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from preflight.config import get_settings
from preflight.db.models import ParaphraseCache, PersonaPool, ProbeResponse, Run
from preflight.llm.anthropic_client import get_client
from preflight.logging import get_logger
from preflight.persona.prompt_template import render_persona_prompt
from preflight.persona.schema import Persona
from preflight.schemas.run import JobPayload
from preflight.schemas.survey import Question, Survey
from preflight.worker.jobs.paraphrase_gen import question_hash
from preflight.worker.queue import JobQueue
from preflight.worker.state import set_run_status

logger = get_logger(__name__)

DEFAULT_SUB_SWARM_SIZE = 200
DEFAULT_BASELINE_SIZE = 1000


def _answer_tool_for(question: Question) -> dict[str, Any]:
    """Build a tool schema appropriate to the question type so the model returns
    a structured response we can store deterministically."""
    schema: dict[str, Any]
    if question.type == "likert_5":
        schema = {"type": "integer", "minimum": 1, "maximum": 5}
    elif question.type == "likert_7":
        schema = {"type": "integer", "minimum": 1, "maximum": 7}
    elif question.type == "nps":
        schema = {"type": "integer", "minimum": 0, "maximum": 10}
    elif question.type == "top_box":
        schema = {"type": "integer", "minimum": 1, "maximum": 5}
    elif question.type == "single_choice":
        n_options = len(question.options or [])
        schema = {"type": "integer", "minimum": 0, "maximum": max(0, n_options - 1)}
    elif question.type == "multi_choice":
        n_options = len(question.options or [])
        schema = {
            "type": "array",
            "items": {"type": "integer", "minimum": 0, "maximum": max(0, n_options - 1)},
            "uniqueItems": True,
        }
    else:
        schema = {"type": "string"}

    return {
        "name": "answer_question",
        "description": "Answer the survey question as the persona described in the system prompt.",
        "input_schema": {
            "type": "object",
            "properties": {
                "response_value": schema,
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["response_value", "confidence"],
        },
    }


def _format_question(question: Question, paraphrase_text: str) -> str:
    parts: list[str] = [paraphrase_text]
    if question.type in ("likert_5",):
        parts.append("Answer 1 (Very dissatisfied) to 5 (Very satisfied).")
    elif question.type == "likert_7":
        parts.append("Answer 1 (Strongly disagree) to 7 (Strongly agree).")
    elif question.type == "nps":
        parts.append("Answer 0 to 10.")
    elif question.type == "top_box":
        parts.append("Answer 1 (Definitely no) to 5 (Definitely yes).")
    elif question.type in ("single_choice", "multi_choice") and question.options:
        formatted = "\n".join(f"{i}. {o}" for i, o in enumerate(question.options))
        parts.append(f"Choose by index:\n{formatted}")
    return "\n\n".join(parts)


def _extract_tool_input(raw: Any) -> dict[str, Any]:
    for block in raw.content:
        if getattr(block, "type", None) == "tool_use":
            return block.input  # type: ignore[no-any-return]
    raise ValueError("no tool_use block in response")


async def _load_pool(session: AsyncSession, audience_hash: str) -> list[Persona]:
    pool_row = await session.get(PersonaPool, audience_hash)
    if pool_row is None:
        raise ValueError(f"persona pool {audience_hash} not found")
    return [Persona.model_validate(p) for p in pool_row.persona_json]


async def _load_paraphrases(
    session: AsyncSession, question: Question
) -> list[dict[str, str]]:
    cached_hash = question_hash(question.text)
    cached = await session.get(ParaphraseCache, cached_hash)
    if cached is None:
        raise ValueError(f"paraphrases for question {question.id} not found in cache")
    return list(cached.paraphrases)


async def _probe_one(
    *,
    persona: Persona,
    question: Question,
    paraphrase_idx: int,
    paraphrase_text: str,
    run_id: uuid.UUID,
    session: AsyncSession,
) -> tuple[str, str, int, dict[str, Any]] | None:
    """Single LLM call. Returns the row to upsert, or None on permanent failure."""
    settings = get_settings()
    client = get_client()
    tool = _answer_tool_for(question)

    user_text = _format_question(question, paraphrase_text)
    system_text = render_persona_prompt(persona)

    try:
        result = await client.message(
            model=settings.anthropic_sonnet_model,
            system=system_text,
            user=user_text,
            purpose="probe_response",
            max_tokens=128,
            temperature=0.7,
            cache_system=True,
            run_id=run_id,
            session=session,
            tools=[tool],
            tool_choice={"type": "tool", "name": "answer_question"},
        )
        tool_input = _extract_tool_input(result.raw)
        return persona.id, question.id, paraphrase_idx, tool_input
    except Exception as exc:
        logger.warning(
            "probe.call_failed",
            persona_id=persona.id,
            question_id=question.id,
            paraphrase_idx=paraphrase_idx,
            error=str(exc),
        )
        return None


async def _persist_responses(
    session: AsyncSession,
    run_id: uuid.UUID,
    rows: list[tuple[str, str, int, dict[str, Any]]],
) -> None:
    if not rows:
        return
    values = [
        {
            "run_id": run_id,
            "persona_id": persona_id,
            "question_id": question_id,
            "paraphrase_idx": idx,
            "response_value": payload,
        }
        for (persona_id, question_id, idx, payload) in rows
    ]
    stmt = pg_insert(ProbeResponse).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["run_id", "persona_id", "question_id", "paraphrase_idx"],
        set_={"response_value": stmt.excluded.response_value},
    )
    await session.execute(stmt)
    await session.commit()


async def _all_question_probes_done(session: AsyncSession, run_id: uuid.UUID) -> bool:
    run = await session.get(Run, run_id)
    if run is None:
        return False
    survey = Survey.model_validate(run.survey_json)
    expected_questions = {
        q.id for q in survey.questions if q.type in {
            "likert_5", "likert_7", "single_choice", "multi_choice", "nps", "top_box"
        }
    }
    if not expected_questions:
        return True
    rows = await session.execute(
        select(ProbeResponse.question_id)
        .where(ProbeResponse.run_id == run_id)
        .distinct()
    )
    seen = {row[0] for row in rows.all()}
    return expected_questions.issubset(seen)


async def handle_run_probe(
    payload: JobPayload,
    session: AsyncSession,
    queue: JobQueue,
) -> None:
    """One job per question. Runs (sub-swarm × K paraphrases) for that question."""
    run = await session.get(Run, payload.run_id)
    if run is None:
        raise ValueError(f"run {payload.run_id} not found")

    if run.status not in ("paraphrases_ready", "probing"):
        await set_run_status(session, payload.run_id, "probing")

    survey = Survey.model_validate(run.survey_json)
    question_id = payload.args["question_id"]
    question = next((q for q in survey.questions if q.id == question_id), None)
    if question is None:
        raise ValueError(f"question {question_id} missing from survey")

    quick_mode = bool(payload.args.get("quick_mode", False))
    sub_swarm_n = 100 if quick_mode else DEFAULT_SUB_SWARM_SIZE
    baseline_n = 500 if quick_mode else DEFAULT_BASELINE_SIZE

    pool = await _load_pool(session, run.audience_hash)
    paraphrases = await _load_paraphrases(session, question)

    baseline_personas = pool[:baseline_n]
    sub_swarm = pool[:sub_swarm_n]

    tasks: list[Any] = []
    for persona in baseline_personas:
        tasks.append(
            _probe_one(
                persona=persona,
                question=question,
                paraphrase_idx=0,
                paraphrase_text=question.text,
                run_id=payload.run_id,
                session=session,
            )
        )
    for persona in sub_swarm:
        for idx, paraphrase in enumerate(paraphrases, start=1):
            tasks.append(
                _probe_one(
                    persona=persona,
                    question=question,
                    paraphrase_idx=idx,
                    paraphrase_text=paraphrase["text"],
                    run_id=payload.run_id,
                    session=session,
                )
            )

    results = await asyncio.gather(*tasks, return_exceptions=False)
    rows = [r for r in results if r is not None]
    await _persist_responses(session, payload.run_id, rows)

    logger.info(
        "job.run_probe.done",
        run_id=str(payload.run_id),
        question_id=question.id,
        rows=len(rows),
        attempted=len(tasks),
    )

    if await _all_question_probes_done(session, payload.run_id):
        await set_run_status(session, payload.run_id, "stats_running")
        await queue.enqueue(job_type="analyze", run_id=payload.run_id)
