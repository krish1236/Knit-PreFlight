"""Pydantic types for analyzer outputs.

These flow into report_composer and end up serialized in the final report card.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["high", "medium", "low", "none"]


class ParaphraseExample(BaseModel):
    paraphrase_idx: int
    text: str
    mean_response: float
    n: int


class ParaphraseShiftFlag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    metric: Literal["wasserstein", "jensen_shannon", "total_variation", "skipped"]
    score: float
    cohens_d: float | None
    n_personas: int
    severity: Severity
    examples: list[ParaphraseExample]
    note: str | None = None
    summary: str = ""


class IRTFlag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    discrimination: float
    interpretation: Literal["poor", "moderate", "strong", "experimental"]
    convergence_ok: bool
    n_personas: int
    severity: Severity
    note: str | None = None
    summary: str = ""


class RedundancyFlag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q_id_a: str
    q_id_b: str
    pearson: float
    spearman: float
    n_personas: int
    severity: Severity
    summary: str = ""


class ScreenerFlag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal[
        "dead_branch",
        "loop",
        "unreachable_question",
        "contradicting_rule",
        "self_loop",
    ]
    description: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    severity: Severity
    summary: str = ""


class QuotaFeasibility(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell: dict[str, Any]
    target_n: int
    estimated_panel_pct: float
    estimated_n_at_target: int
    severity: Severity
    summary: str = ""


class CalibrationDisclosure(BaseModel):
    f1_overall: float | None = None
    benchmark: str = "not_yet_run"
    version: str = "dev"
