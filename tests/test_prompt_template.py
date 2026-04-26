"""Persona prompt rendering."""

from __future__ import annotations

from preflight.persona.prompt_template import render_persona_prompt
from preflight.persona.schema import (
    Demographic,
    Persona,
    ResponseStyleTraits,
)


def _make_persona(**overrides: object) -> Persona:
    defaults = {
        "id": "p_test",
        "demographic": Demographic(
            age=35,
            sex="female",
            education="college",
            income=85_000,
            state="NY",
            race="white",
            marital="married",
        ),
        "response_style": ResponseStyleTraits(
            effort_level="satisficer",
            acquiescence="high",
            extreme_response="medium",
            social_desirability="medium",
            reading_level="college",
            device="mobile",
        ),
    }
    defaults.update(overrides)  # type: ignore[arg-type]
    return Persona(**defaults)  # type: ignore[arg-type]


def test_prompt_includes_demographic_facts() -> None:
    p = _make_persona()
    text = render_persona_prompt(p)
    assert "35-year-old" in text
    assert "woman" in text
    assert "NY" in text


def test_satisficer_phrase_present() -> None:
    p = _make_persona()
    text = render_persona_prompt(p)
    assert "satisfic" in text.lower() or "good enough" in text.lower()


def test_high_acquiescence_phrase_present() -> None:
    p = _make_persona()
    text = render_persona_prompt(p)
    assert "agree" in text.lower()


def test_optimizer_phrase_for_optimizer_style() -> None:
    p = _make_persona(
        response_style=ResponseStyleTraits(
            effort_level="optimizer",
            acquiescence="low",
            extreme_response="medium",
            social_desirability="low",
            reading_level="college",
            device="desktop",
        )
    )
    text = render_persona_prompt(p)
    assert "carefully" in text.lower() or "accurate" in text.lower()


def test_no_break_character_directive_present() -> None:
    p = _make_persona()
    text = render_persona_prompt(p)
    assert "do not break character" in text.lower()
