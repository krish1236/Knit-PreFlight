"""Sample cognitive response-style traits from a parameterized config.

These traits are independent of demographics in v0 (a documented simplification;
v1 can condition reading_level on education, device on age, etc.).
"""

from __future__ import annotations

import random
from typing import TypeVar

from preflight.persona.schema import ResponseStyleConfig, ResponseStyleTraits

T = TypeVar("T", bound=str)


def _weighted_choice(rng: random.Random, distribution: dict[T, float]) -> T:
    keys = list(distribution.keys())
    weights = list(distribution.values())
    return rng.choices(keys, weights=weights, k=1)[0]


def sample_traits(rng: random.Random, config: ResponseStyleConfig) -> ResponseStyleTraits:
    return ResponseStyleTraits(
        effort_level=_weighted_choice(rng, config.effort_level),
        acquiescence=_weighted_choice(rng, config.acquiescence),
        extreme_response=_weighted_choice(rng, config.extreme_response),
        social_desirability=_weighted_choice(rng, config.social_desirability),
        reading_level=_weighted_choice(rng, config.reading_level),
        device=_weighted_choice(rng, config.device),
    )
