"""Response-style trait sampling produces correct distributions."""

from __future__ import annotations

import random
from collections import Counter

from preflight.persona.schema import ResponseStyleConfig
from preflight.persona.style_composer import sample_traits


def test_sampled_distribution_matches_config_within_tolerance() -> None:
    rng = random.Random(42)
    config = ResponseStyleConfig()
    n = 10_000
    samples = [sample_traits(rng, config) for _ in range(n)]

    effort_counts = Counter(s.effort_level for s in samples)
    assert abs(effort_counts["optimizer"] / n - 0.70) < 0.02
    assert abs(effort_counts["satisficer"] / n - 0.20) < 0.02
    assert abs(effort_counts["speeder"] / n - 0.10) < 0.02


def test_sampling_is_deterministic_given_seed() -> None:
    config = ResponseStyleConfig()
    rng1 = random.Random(123)
    rng2 = random.Random(123)
    s1 = [sample_traits(rng1, config) for _ in range(100)]
    s2 = [sample_traits(rng2, config) for _ in range(100)]
    assert s1 == s2


def test_custom_config_respected() -> None:
    config = ResponseStyleConfig(
        effort_level={"optimizer": 0.0, "satisficer": 1.0, "speeder": 0.0}
    )
    rng = random.Random(42)
    samples = [sample_traits(rng, config) for _ in range(500)]
    assert all(s.effort_level == "satisficer" for s in samples)
