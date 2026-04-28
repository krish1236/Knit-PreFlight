"""Load sample surveys from disk and seed them into the runs table.

Sample surveys live in `seeds/sample_surveys/*.json`. Each survey is loaded
once at deploy time and inserted into `runs` with `is_sample=true` and
`status='pending'`. The frontend's GET /samples endpoint lists them; the
demo flow runs each through the full pipeline once so the report card is
cached for the 60-second test path.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from preflight.db.models import Run
from preflight.logging import get_logger
from preflight.persona.pool_generator import audience_hash
from preflight.persona.schema import ResponseStyleConfig
from preflight.schemas.survey import Survey

logger = get_logger(__name__)

SEEDS_DIR = Path("seeds/sample_surveys")


def load_sample_files() -> list[tuple[str, dict]]:
    """Return a sorted list of (slug, survey_dict) — slug derived from filename stem."""
    if not SEEDS_DIR.exists():
        return []
    out: list[tuple[str, dict]] = []
    for path in sorted(SEEDS_DIR.glob("*.json")):
        slug = path.stem
        with path.open() as f:
            out.append((slug, json.load(f)))
    return out


async def seed_samples(
    session: AsyncSession,
    *,
    n_per_pool: int = 1000,
    seed: int = 42,
) -> list[uuid.UUID]:
    """Insert any sample surveys not already present. Returns the run_ids touched."""
    inserted: list[uuid.UUID] = []
    for slug, survey_dict in load_sample_files():
        survey = Survey.model_validate(survey_dict)

        existing = await session.execute(
            select(Run.id).where(Run.survey_id == survey.id, Run.is_sample.is_(True))
        )
        if existing.first() is not None:
            logger.info("samples.already_seeded", slug=slug, survey_id=survey.id)
            continue

        h = audience_hash(survey.audience, ResponseStyleConfig(), n=n_per_pool, seed=seed)
        run = Run(
            id=uuid.uuid4(),
            survey_id=survey.id,
            survey_json=survey.model_dump(mode="json"),
            status="pending",
            audience_hash=h,
            is_sample=True,
        )
        session.add(run)
        await session.commit()
        inserted.append(run.id)
        logger.info("samples.seeded", slug=slug, survey_id=survey.id, run_id=str(run.id))
    return inserted
