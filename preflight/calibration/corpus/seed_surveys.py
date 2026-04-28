"""Curated clean survey instruments used as the calibration corpus baseline.

These are deliberately well-formed surveys that should produce zero or near-
zero defect flags from Pre-Flight. Defect injectors then transform each one
to produce defect-positive variants for F1 measurement.

The corpus is generated programmatically rather than seeded from disk so
that it scales with `n_surveys` and so that public reproducibility is one
import away.
"""

from __future__ import annotations

import random

from preflight.persona.schema import (
    AgeRange,
    AudienceConstraints,
    GeoConstraint,
    IncomeRange,
)
from preflight.schemas.survey import (
    Brief,
    Fielding,
    Question,
    Survey,
)

CATEGORIES = [
    "mobile_carrier",
    "streaming_service",
    "online_retail",
    "fitness_app",
    "food_delivery",
    "credit_card",
    "automotive",
    "athletic_apparel",
    "home_insurance",
    "ride_share",
]

SUBJECTS = {
    "mobile_carrier": "your current mobile carrier",
    "streaming_service": "your primary streaming subscription",
    "online_retail": "your most-used online retail store",
    "fitness_app": "your fitness tracking app",
    "food_delivery": "your most-used food delivery service",
    "credit_card": "your primary credit card",
    "automotive": "your current vehicle",
    "athletic_apparel": "the athletic apparel brand you wear most",
    "home_insurance": "your home or renters insurance provider",
    "ride_share": "your most-used ride-share service",
}


def _build_survey(idx: int, category: str, rng: random.Random) -> Survey:
    subject = SUBJECTS[category]
    audience = AudienceConstraints(
        age_range=AgeRange(min=rng.choice([18, 21, 25]), max=rng.choice([54, 60, 65])),
        income_range=IncomeRange(min=rng.choice([0, 35_000, 50_000])),
        geo=GeoConstraint(country="US"),
    )

    questions = [
        Question(
            id="Q1",
            type="likert_5",
            text=f"How satisfied are you with {subject}?",
            scale_labels=["Very dissatisfied", "Dissatisfied", "Neutral", "Satisfied", "Very satisfied"],
        ),
        Question(
            id="Q2",
            type="nps",
            text=f"How likely are you to recommend {subject} to a friend?",
        ),
        Question(
            id="Q3",
            type="likert_5",
            text=f"How well does {subject} meet your needs?",
            scale_labels=["Not at all", "Slightly", "Moderately", "Mostly", "Completely"],
        ),
        Question(
            id="Q4",
            type="single_choice",
            text=f"What matters most when choosing a {category.replace('_', ' ')}?",
            options=["Price", "Quality", "Customer service", "Brand reputation", "Convenience"],
        ),
        Question(
            id="Q5",
            type="likert_5",
            text=f"How would you rate the value for money of {subject}?",
            scale_labels=["Very poor", "Poor", "Fair", "Good", "Excellent"],
        ),
        Question(
            id="Q6",
            type="top_box",
            text=f"Would you continue using {subject} over the next 12 months?",
        ),
    ]

    brief = Brief(
        objectives=[f"track quarterly satisfaction with {category} brands"],
        audience_criteria=f"US adults using a {category.replace('_', ' ')}",
        business_context="quarterly tracker baseline",
        hypothesis="satisfaction correlates with retention",
        scope="national, English-only",
        success_criteria=["min 200 responses", "completion under 8 min"],
    )

    return Survey(
        id=f"clean-{idx:03d}-{category}",
        version="0.1",
        brief=brief,
        audience=audience,
        questions=questions,
        fielding=Fielding(panel_source="knit_panel", target_n=400, est_completion_minutes=6),
    )


def generate_clean_corpus(n: int = 30, *, seed: int = 7) -> list[Survey]:
    """Return n clean, defect-free surveys spanning the category list."""
    rng = random.Random(seed)
    out: list[Survey] = []
    for i in range(n):
        cat = CATEGORIES[i % len(CATEGORIES)]
        out.append(_build_survey(i, cat, rng))
    return out
