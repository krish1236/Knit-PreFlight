"""Generate K=5 axis-constrained paraphrases per question.

Uses Haiku 4.5 with high temperature for diversity. Validates each paraphrase
against the original via embedding cosine similarity, and validates pairwise
diversity within the K to prevent collapse. Caches by question_text hash.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

import numpy as np
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from preflight.config import get_settings
from preflight.db.models import ParaphraseCache, Run
from preflight.embeddings import embed, pairwise_cosine
from preflight.llm.anthropic_client import get_client
from preflight.logging import get_logger
from preflight.schemas.run import JobPayload
from preflight.schemas.survey import Question, Survey
from preflight.worker.queue import JobQueue
from preflight.worker.state import set_run_status

logger = get_logger(__name__)

K_PARAPHRASES = 5
MAX_RETRIES = 3
EQUIVALENCE_FLOOR = 0.85
DIVERSITY_FLOOR = 0.70
DIVERSITY_CEIL = 0.95

PARAPHRASEABLE_TYPES = {
    "likert_5", "likert_7", "single_choice", "multi_choice", "nps", "top_box"
}

PARAPHRASE_SYSTEM = """You are a survey methodology expert generating semantically-equivalent paraphrases of survey questions for instrument stress-testing.

Generate exactly 5 paraphrases of the given question. Each paraphrase must:
- preserve the question's meaning and answerability with the same answer scale
- vary on a different primary axis from the others

The 5 axes (one per paraphrase, in this order):
1. sentence_structure — switch active/passive, restructure clauses
2. quantifier — alternate words like often/frequently/regularly/usually where present
3. politeness — vary scaffolding (e.g., "Please rate" vs "How would you rate")
4. framing — neutral vs slightly affirmative framing while preserving the question
5. word_substitution — replace key terms with denotational synonyms

Return only the structured tool call. No commentary."""

PARAPHRASE_TOOL = {
    "name": "submit_paraphrases",
    "description": "Submit 5 paraphrases of the question, one per axis.",
    "input_schema": {
        "type": "object",
        "properties": {
            "paraphrases": {
                "type": "array",
                "minItems": K_PARAPHRASES,
                "maxItems": K_PARAPHRASES,
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "axis": {
                            "type": "string",
                            "enum": [
                                "sentence_structure",
                                "quantifier",
                                "politeness",
                                "framing",
                                "word_substitution",
                            ],
                        },
                    },
                    "required": ["text", "axis"],
                },
            }
        },
        "required": ["paraphrases"],
    },
}


def question_hash(question_text: str, version: str = "v1") -> str:
    return hashlib.sha256(f"{version}|{question_text}".encode()).hexdigest()


def _extract_tool_input(raw: Any) -> dict[str, Any]:
    for block in raw.content:
        if getattr(block, "type", None) == "tool_use":
            return block.input  # type: ignore[no-any-return]
    raise ValueError("no tool_use block in response")


def _validate_paraphrases(
    original: str, paraphrases: list[str]
) -> tuple[bool, str]:
    """Returns (ok, reason). All embeddings are L2-normalized."""
    all_texts = [original] + paraphrases
    vectors = embed(all_texts)

    original_vec = vectors[0]
    paraphrase_vecs = vectors[1:]

    sims_to_original = paraphrase_vecs @ original_vec
    if (sims_to_original < EQUIVALENCE_FLOOR).any():
        return False, f"equivalence_below_floor: min={sims_to_original.min():.3f}"

    pairwise = pairwise_cosine(paraphrase_vecs)
    triu_mask = np.triu(np.ones_like(pairwise, dtype=bool), k=1)
    pair_values = pairwise[triu_mask]
    if (pair_values > DIVERSITY_CEIL).any():
        return False, f"pair_too_similar: max={pair_values.max():.3f}"
    if (pair_values < DIVERSITY_FLOOR).any():
        return False, f"pair_too_divergent: min={pair_values.min():.3f}"

    return True, "ok"


async def _generate_for_question(
    question: Question,
    run_id: str,
    session: AsyncSession,
) -> list[dict[str, str]]:
    """Generate, validate, retry up to MAX_RETRIES. Returns the list of paraphrases."""
    settings = get_settings()
    client = get_client()

    cached_hash = question_hash(question.text)
    existing = await session.get(ParaphraseCache, cached_hash)
    if existing is not None:
        logger.info("paraphrase.cache_hit", question_id=question.id)
        return list(existing.paraphrases)

    user_prompt = f"Question to paraphrase:\n\n{question.text}"

    last_reason = ""
    for attempt in range(1, MAX_RETRIES + 1):
        result = await client.message(
            model=settings.anthropic_haiku_model,
            system=PARAPHRASE_SYSTEM,
            user=user_prompt,
            purpose="paraphrase_gen",
            max_tokens=1024,
            temperature=0.9,
            cache_system=True,
            session=session,
            tools=[PARAPHRASE_TOOL],
            tool_choice={"type": "tool", "name": "submit_paraphrases"},
        )
        try:
            tool_input = _extract_tool_input(result.raw)
        except ValueError:
            last_reason = "no_tool_use_block"
            continue

        paraphrases_data = tool_input.get("paraphrases", [])
        texts = [p["text"] for p in paraphrases_data]

        ok, reason = _validate_paraphrases(question.text, texts)
        if ok:
            payload = [
                {"text": p["text"], "axis": p["axis"], "validated": True}
                for p in paraphrases_data
            ]
            stmt = pg_insert(ParaphraseCache).values(
                question_hash=cached_hash, paraphrases=payload
            )
            stmt = stmt.on_conflict_do_nothing(index_elements=["question_hash"])
            await session.execute(stmt)
            await session.commit()
            logger.info(
                "paraphrase.generated",
                question_id=question.id,
                attempt=attempt,
                run_id=run_id,
            )
            return payload

        last_reason = reason
        logger.warning(
            "paraphrase.validation_failed",
            question_id=question.id,
            attempt=attempt,
            reason=reason,
        )

    logger.error(
        "paraphrase.giving_up",
        question_id=question.id,
        run_id=run_id,
        last_reason=last_reason,
    )
    fallback = [
        {"text": question.text, "axis": "fallback_original", "validated": False}
        for _ in range(K_PARAPHRASES)
    ]
    return fallback


async def handle_gen_paraphrases(
    payload: JobPayload,
    session: AsyncSession,
    queue: JobQueue,
) -> None:
    run = await session.get(Run, payload.run_id)
    if run is None:
        raise ValueError(f"run {payload.run_id} not found")

    survey = Survey.model_validate(run.survey_json)
    questions = [q for q in survey.questions if q.type in PARAPHRASEABLE_TYPES]

    sem = asyncio.Semaphore(8)

    async def _gen(q: Question) -> None:
        async with sem:
            await _generate_for_question(q, str(payload.run_id), session)

    await asyncio.gather(*(_gen(q) for q in questions))

    logger.info(
        "job.gen_paraphrases.done",
        run_id=str(payload.run_id),
        questions=len(questions),
    )

    await set_run_status(session, payload.run_id, "paraphrases_ready")

    for question in questions:
        await queue.enqueue(
            job_type="run_probe",
            run_id=payload.run_id,
            args={"question_id": question.id},
        )

    if not questions:
        await set_run_status(session, payload.run_id, "probing")
