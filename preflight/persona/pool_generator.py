"""End-to-end persona pool generation with audience-hash caching."""

from __future__ import annotations

import hashlib
import json
import random
import uuid

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from preflight.db.models import PersonaPool
from preflight.logging import get_logger
from preflight.persona.pums_loader import (
    MAR_LABELS,
    RAC1P_LABELS,
    SCHL_TO_LABEL,
    STATE_FIPS_TO_USPS,
    filter_by_audience,
    load_pums,
    weighted_sample,
)
from preflight.persona.schema import (
    AudienceConstraints,
    Demographic,
    Persona,
    ResponseStyleConfig,
)
from preflight.persona.style_composer import sample_traits

logger = get_logger(__name__)

POOL_VERSION = "v1"


def audience_hash(
    audience: AudienceConstraints,
    style_config: ResponseStyleConfig,
    n: int,
    seed: int,
) -> str:
    payload = {
        "audience": audience.model_dump(mode="json"),
        "style": style_config.model_dump(mode="json"),
        "n": n,
        "seed": seed,
        "version": POOL_VERSION,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def _row_to_demographic(row: pd.Series) -> Demographic:
    return Demographic(
        age=int(row["AGEP"]),
        sex="female" if int(row["SEX"]) == 2 else "male",
        education=SCHL_TO_LABEL.get(int(row["SCHL"]), "less_than_hs"),
        income=int(row["PINCP"]) if pd.notna(row["PINCP"]) else None,
        state=STATE_FIPS_TO_USPS.get(int(row["ST"]), "??"),
        race=RAC1P_LABELS.get(int(row["RAC1P"]), "other"),
        marital=MAR_LABELS.get(int(row["MAR"]), "never_married"),
    )


def generate_pool_in_memory(
    audience: AudienceConstraints,
    style_config: ResponseStyleConfig,
    n: int = 1000,
    seed: int = 42,
) -> list[Persona]:
    """Pure-function pool generation; no database side effects."""
    pums = load_pums()
    filtered = filter_by_audience(pums, audience)

    if filtered.empty:
        raise ValueError("audience filter matched zero PUMS rows; loosen constraints")

    sampled = weighted_sample(filtered, n=n, seed=seed)

    rng = random.Random(seed)
    personas: list[Persona] = []
    for i, row in enumerate(sampled.itertuples(index=False)):
        row_series = pd.Series(row._asdict())
        demographic = _row_to_demographic(row_series)
        traits = sample_traits(rng, style_config)
        personas.append(
            Persona(
                id=f"p_{i:04d}_{uuid.uuid4().hex[:8]}",
                demographic=demographic,
                response_style=traits,
            )
        )
    return personas


async def get_or_create_pool(
    session: AsyncSession,
    audience: AudienceConstraints,
    style_config: ResponseStyleConfig | None = None,
    n: int = 1000,
    seed: int = 42,
) -> tuple[list[Persona], bool]:
    """Return (personas, cache_hit). Cached by audience+style+n+seed hash."""
    style_config = style_config or ResponseStyleConfig()
    h = audience_hash(audience, style_config, n, seed)

    existing = await session.execute(select(PersonaPool).where(PersonaPool.audience_hash == h))
    row = existing.scalar_one_or_none()
    if row is not None:
        personas = [Persona.model_validate(p) for p in row.persona_json]
        logger.info("persona_pool.cache_hit", audience_hash=h, n=len(personas))
        return personas, True

    personas = generate_pool_in_memory(audience, style_config, n=n, seed=seed)

    stmt = pg_insert(PersonaPool).values(
        audience_hash=h,
        persona_count=len(personas),
        persona_json=[p.model_dump(mode="json") for p in personas],
        response_style_config=style_config.model_dump(mode="json"),
        seed=seed,
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=["audience_hash"])
    await session.execute(stmt)
    await session.commit()

    logger.info("persona_pool.cache_miss_created", audience_hash=h, n=len(personas))
    return personas, False
