"""SQLAlchemy ORM models for Pre-Flight persistence layer."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSONB, list[Any]: JSONB}


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    survey_id: Mapped[str] = mapped_column(String(128), nullable=False)
    survey_json: Mapped[dict[str, Any]] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    audience_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_sample: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    report: Mapped[Report | None] = relationship(back_populates="run", uselist=False)

    __table_args__ = (Index("ix_runs_survey_created", "survey_id", "created_at"),)


class PersonaPool(Base):
    __tablename__ = "persona_pools"

    audience_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    persona_count: Mapped[int] = mapped_column(Integer, nullable=False)
    persona_json: Mapped[list[Any]] = mapped_column(nullable=False)
    response_style_config: Mapped[dict[str, Any]] = mapped_column(nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False, default=42)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ParaphraseCache(Base):
    __tablename__ = "paraphrase_cache"

    question_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    paraphrases: Mapped[list[Any]] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ProbeResponse(Base):
    __tablename__ = "probe_responses"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), primary_key=True
    )
    persona_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    question_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    paraphrase_idx: Mapped[int] = mapped_column(Integer, primary_key=True)
    response_value: Mapped[dict[str, Any]] = mapped_column(nullable=False)

    __table_args__ = (Index("ix_probe_run_question", "run_id", "question_id"),)


class Report(Base):
    __tablename__ = "reports"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), primary_key=True
    )
    report_json: Mapped[dict[str, Any]] = mapped_column(nullable=False)
    calibration_version: Mapped[str] = mapped_column(String(64), nullable=False, default="dev")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    run: Mapped[Run] = relationship(back_populates="report")


class CalibrationSurvey(Base):
    __tablename__ = "calibration_surveys"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    survey_json: Mapped[dict[str, Any]] = mapped_column(nullable=False)
    defect_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class CalibrationRun(Base):
    __tablename__ = "calibration_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    git_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    f1_overall: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    f1_per_class: Mapped[dict[str, Any]] = mapped_column(nullable=False)
    n_surveys: Mapped[int] = mapped_column(Integer, nullable=False)


class LLMCall(Base):
    """Per-call cost ledger. Aggregated for spend tracking and run-level cost reporting."""

    __tablename__ = "llm_calls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("ix_llmcalls_run_created", "run_id", "created_at"),)
