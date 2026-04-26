"""Knit-shaped survey JSON — the input contract for Pre-Flight runs.

Modeled on Knit's documented 5-phase workflow (brief → survey → analysis plan →
fielding → analysis → reporting). Field names are ours; an adapter layer can
translate from Knit's internal schema once that becomes available.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from preflight.persona.schema import AudienceConstraints

QuestionType = Literal[
    "likert_5",
    "likert_7",
    "single_choice",
    "multi_choice",
    "nps",
    "top_box",
    "open_end",
    "stimulus_block",
    "video_open_end",
]

ConditionalOperator = Literal["==", "!=", ">", ">=", "<", "<=", "in", "not_in"]


class Conditional(BaseModel):
    q_id: str
    operator: ConditionalOperator
    value: Any


class Stimulus(BaseModel):
    kind: Literal["concept", "ad", "package", "storyboard", "ux_screen"]
    description: str
    url: str | None = None


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: QuestionType
    text: str
    options: list[str] | None = None
    scale_labels: list[str] | None = None
    stimulus: Stimulus | None = None
    evaluation_axes: list[str] | None = None
    conditional_on: Conditional | None = None


class Brief(BaseModel):
    objectives: list[str]
    audience_criteria: str
    business_context: str = ""
    hypothesis: str = ""
    scope: str = ""
    success_criteria: list[str] = Field(default_factory=list)


class ScreenerRule(BaseModel):
    q_id: str
    if_value_in: list[Any] | None = None
    if_value_op: ConditionalOperator | None = None
    if_value: Any = None
    action: Literal["terminate", "qualify"]


class Screener(BaseModel):
    rules: list[ScreenerRule] = Field(default_factory=list)


class QuotaCell(BaseModel):
    cell: dict[str, Any]
    target_n: int


class Fielding(BaseModel):
    panel_source: Literal["knit_panel", "crm", "hybrid"] = "knit_panel"
    target_n: int = 800
    est_completion_minutes: int = 12


class Survey(BaseModel):
    """The input artifact uploaded to Pre-Flight."""

    model_config = ConfigDict(extra="forbid")

    id: str
    version: str = "0.1"
    brief: Brief
    audience: AudienceConstraints
    questions: list[Question]
    screener: Screener = Field(default_factory=Screener)
    quotas: list[QuotaCell] = Field(default_factory=list)
    fielding: Fielding = Field(default_factory=Fielding)
