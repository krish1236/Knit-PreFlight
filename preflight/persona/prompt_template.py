"""Persona prompt template designed for ephemeral prompt caching.

The system message is the persona description (cached). The user message holds
the question being probed (uncached, varies per call). This pattern minimizes
the per-call billable input tokens to roughly the question content alone after
the first call within the cache TTL.
"""

from __future__ import annotations

from preflight.persona.schema import Persona, ResponseStyleTraits

EFFORT_DESCRIPTIONS = {
    "optimizer": (
        "You read survey questions carefully. You consider each option before answering "
        "and try to give the most accurate response."
    ),
    "satisficer": (
        "You skim survey questions and pick a 'good enough' answer rather than thinking "
        "hard about each one. You sometimes select the first reasonable option."
    ),
    "speeder": (
        "You rush through surveys to finish quickly. You read minimally and often pick "
        "the first or middle option without much thought."
    ),
}

ACQUIESCENCE_DESCRIPTIONS = {
    "low": "",
    "medium": "You have a mild tendency to agree with statements when uncertain.",
    "high": (
        "You tend to agree with statements rather than disagree, especially when you're "
        "not sure. 'Yes' feels easier than 'No' to you."
    ),
}

EXTREME_RESPONSE_DESCRIPTIONS = {
    "low": "You tend to pick middle options on rating scales.",
    "medium": "",
    "high": "You tend to pick endpoints (1 or 7) on rating scales rather than middle values.",
}

SOCIAL_DESIRABILITY_DESCRIPTIONS = {
    "low": "",
    "medium": "You sometimes adjust answers to seem reasonable to others.",
    "high": (
        "You strongly prefer answers that make you look good to others. You under-report "
        "behaviors you think are judged negatively."
    ),
}

READING_LEVEL_DESCRIPTIONS = {
    "college": "You read fluently and parse complex survey wording without difficulty.",
    "hs": (
        "You read at a high-school level. Long or jargon-heavy questions take you longer "
        "and you sometimes skim past complex phrasing."
    ),
    "low": (
        "You read slowly. Long or technical questions are hard for you to parse. You "
        "sometimes guess at meanings of unfamiliar words and pick a default answer."
    ),
}

DEVICE_DESCRIPTIONS = {
    "mobile": (
        "You're taking this survey on a phone. Long matrix questions are awkward to read "
        "and you may rush through them."
    ),
    "desktop": "You're taking this survey on a desktop computer with a full screen.",
}


def _education_label(code: str) -> str:
    return {
        "less_than_hs": "did not finish high school",
        "hs": "have a high school diploma",
        "some_college": "have some college education",
        "college": "have a college degree",
        "graduate": "have a graduate degree",
    }.get(code, code)


def _race_phrase(code: str) -> str:
    return {
        "white": "white",
        "black": "Black",
        "asian": "Asian",
        "native": "Native American",
        "pacific_islander": "Pacific Islander",
        "other": "of another race",
        "multi": "of mixed race",
    }.get(code, code)


def _marital_phrase(code: str) -> str:
    return {
        "married": "married",
        "widowed": "widowed",
        "divorced": "divorced",
        "separated": "separated",
        "never_married": "never married",
    }.get(code, code)


def _income_band(income: int | None) -> str:
    if income is None:
        return "no reported income"
    if income < 25_000:
        return "lower-income"
    if income < 60_000:
        return "lower-middle-income"
    if income < 120_000:
        return "middle-income"
    if income < 200_000:
        return "upper-middle-income"
    return "high-income"


def _style_paragraph(style: ResponseStyleTraits) -> str:
    parts = [
        EFFORT_DESCRIPTIONS[style.effort_level],
        ACQUIESCENCE_DESCRIPTIONS[style.acquiescence],
        EXTREME_RESPONSE_DESCRIPTIONS[style.extreme_response],
        SOCIAL_DESIRABILITY_DESCRIPTIONS[style.social_desirability],
        READING_LEVEL_DESCRIPTIONS[style.reading_level],
        DEVICE_DESCRIPTIONS[style.device],
    ]
    return " ".join(p for p in parts if p)


def render_persona_prompt(persona: Persona) -> str:
    """Render the cached system message describing the persona.

    Returns at least ~1024 tokens of context where possible (Anthropic ephemeral
    cache minimum); padding via response-style detail is intentional.
    """
    d = persona.demographic
    sex_phrase = "woman" if d.sex == "female" else "man"
    race_phrase = _race_phrase(d.race)
    edu_phrase = _education_label(d.education)
    mar_phrase = _marital_phrase(d.marital)
    income_band = _income_band(d.income)

    demographic_para = (
        f"You are a {d.age}-year-old {race_phrase} {sex_phrase} living in {d.state}. "
        f"You {edu_phrase} and are {mar_phrase}. "
        f"You are in the {income_band} bracket."
    )
    style_para = _style_paragraph(persona.response_style)

    framing = (
        "You are answering a survey question. Respond as this specific person would, "
        "informed by their background and how they tend to take surveys. Be authentic to "
        "the persona — including any tendencies toward satisficing, agreement bias, or "
        "extreme/middle response patterns described above. Do not break character. Return "
        "only the structured answer requested; no preamble, no explanation."
    )

    return "\n\n".join([demographic_para, style_para, framing])
