"""End-to-end persona pool generation."""

from __future__ import annotations

from preflight.persona.pool_generator import (
    audience_hash,
    generate_pool_in_memory,
)
from preflight.persona.schema import (
    AgeRange,
    AudienceConstraints,
    ResponseStyleConfig,
)


def test_pool_size_matches_request() -> None:
    audience = AudienceConstraints(age_range=AgeRange(min=25, max=54))
    pool = generate_pool_in_memory(audience, ResponseStyleConfig(), n=200, seed=42)
    assert len(pool) == 200


def test_pool_personas_have_complete_fields() -> None:
    audience = AudienceConstraints(age_range=AgeRange(min=25, max=54))
    pool = generate_pool_in_memory(audience, ResponseStyleConfig(), n=50, seed=42)
    for p in pool:
        assert p.id
        assert 25 <= p.demographic.age <= 54
        assert p.demographic.sex in ("male", "female")
        assert p.demographic.state
        assert p.response_style.effort_level in ("optimizer", "satisficer", "speeder")


def test_pool_generation_deterministic() -> None:
    audience = AudienceConstraints(age_range=AgeRange(min=25, max=54))
    p1 = generate_pool_in_memory(audience, ResponseStyleConfig(), n=20, seed=99)
    p2 = generate_pool_in_memory(audience, ResponseStyleConfig(), n=20, seed=99)
    # IDs include random uuid suffixes so they differ; demographics + styles must match
    for a, b in zip(p1, p2):
        assert a.demographic == b.demographic
        assert a.response_style == b.response_style


def test_audience_hash_stable() -> None:
    audience = AudienceConstraints(age_range=AgeRange(min=25, max=54))
    config = ResponseStyleConfig()
    h1 = audience_hash(audience, config, n=100, seed=42)
    h2 = audience_hash(audience, config, n=100, seed=42)
    assert h1 == h2


def test_audience_hash_changes_with_n() -> None:
    audience = AudienceConstraints(age_range=AgeRange(min=25, max=54))
    config = ResponseStyleConfig()
    assert audience_hash(audience, config, n=100, seed=42) != audience_hash(
        audience, config, n=500, seed=42
    )


def test_audience_hash_changes_with_audience() -> None:
    a1 = AudienceConstraints(age_range=AgeRange(min=25, max=54))
    a2 = AudienceConstraints(age_range=AgeRange(min=18, max=65))
    config = ResponseStyleConfig()
    assert audience_hash(a1, config, n=100, seed=42) != audience_hash(
        a2, config, n=100, seed=42
    )
