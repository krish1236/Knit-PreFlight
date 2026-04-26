"""Pydantic schemas for audience constraints, response-style traits, and personas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


EffortLevel = Literal["optimizer", "satisficer", "speeder"]
LowMedHigh = Literal["low", "medium", "high"]
ReadingLevel = Literal["college", "hs", "low"]
DeviceContext = Literal["mobile", "desktop"]


class AgeRange(BaseModel):
    min: int = Field(ge=0, le=120)
    max: int = Field(ge=0, le=120)


class IncomeRange(BaseModel):
    min: int | None = None
    max: int | None = None


class GeoConstraint(BaseModel):
    country: str = "US"
    states: list[str] = Field(default_factory=list)


class AudienceConstraints(BaseModel):
    """Translated form of the brief's audience criteria."""

    model_config = ConfigDict(frozen=True)

    age_range: AgeRange = AgeRange(min=18, max=65)
    genders: list[Literal["any", "male", "female"]] = Field(default_factory=lambda: ["any"])
    income_range: IncomeRange = IncomeRange()
    education_min: Literal["any", "hs", "some_college", "college", "graduate"] = "any"
    geo: GeoConstraint = GeoConstraint()
    behavioral_tags: list[str] = Field(default_factory=list)


class ResponseStyleConfig(BaseModel):
    """Distribution config for cognitive response-style sampling.

    Defaults from published market-research literature (POQ satisficing 10-20%,
    SurveyMonkey research on speeders, ESS on acquiescence).
    """

    model_config = ConfigDict(frozen=True)

    effort_level: dict[EffortLevel, float] = Field(
        default_factory=lambda: {"optimizer": 0.70, "satisficer": 0.20, "speeder": 0.10}
    )
    acquiescence: dict[LowMedHigh, float] = Field(
        default_factory=lambda: {"low": 0.55, "medium": 0.30, "high": 0.15}
    )
    extreme_response: dict[LowMedHigh, float] = Field(
        default_factory=lambda: {"low": 0.60, "medium": 0.30, "high": 0.10}
    )
    social_desirability: dict[LowMedHigh, float] = Field(
        default_factory=lambda: {"low": 0.50, "medium": 0.35, "high": 0.15}
    )
    reading_level: dict[ReadingLevel, float] = Field(
        default_factory=lambda: {"college": 0.40, "hs": 0.45, "low": 0.15}
    )
    device: dict[DeviceContext, float] = Field(
        default_factory=lambda: {"mobile": 0.65, "desktop": 0.35}
    )


class ResponseStyleTraits(BaseModel):
    effort_level: EffortLevel
    acquiescence: LowMedHigh
    extreme_response: LowMedHigh
    social_desirability: LowMedHigh
    reading_level: ReadingLevel
    device: DeviceContext


class Demographic(BaseModel):
    age: int
    sex: Literal["male", "female"]
    education: str
    income: int | None
    state: str
    race: str
    marital: str


class Persona(BaseModel):
    id: str
    demographic: Demographic
    response_style: ResponseStyleTraits
