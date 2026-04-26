"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("survey_id", sa.String(length=128), nullable=False),
        sa.Column("survey_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("audience_hash", sa.String(length=64), nullable=False),
        sa.Column("is_sample", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_runs_survey_created", "runs", ["survey_id", "created_at"])

    op.create_table(
        "persona_pools",
        sa.Column("audience_hash", sa.String(length=64), nullable=False),
        sa.Column("persona_count", sa.Integer(), nullable=False),
        sa.Column("persona_json", postgresql.JSONB(), nullable=False),
        sa.Column("response_style_config", postgresql.JSONB(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False, server_default="42"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("audience_hash"),
    )

    op.create_table(
        "paraphrase_cache",
        sa.Column("question_hash", sa.String(length=64), nullable=False),
        sa.Column("paraphrases", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("question_hash"),
    )

    op.create_table(
        "probe_responses",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("persona_id", sa.String(length=64), nullable=False),
        sa.Column("question_id", sa.String(length=64), nullable=False),
        sa.Column("paraphrase_idx", sa.Integer(), nullable=False),
        sa.Column("response_value", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("run_id", "persona_id", "question_id", "paraphrase_idx"),
    )
    op.create_index("ix_probe_run_question", "probe_responses", ["run_id", "question_id"])

    op.create_table(
        "reports",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_json", postgresql.JSONB(), nullable=False),
        sa.Column("calibration_version", sa.String(length=64), nullable=False, server_default="dev"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("run_id"),
    )

    op.create_table(
        "calibration_surveys",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("survey_json", postgresql.JSONB(), nullable=False),
        sa.Column("defect_class", sa.String(length=64), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=True),
        sa.Column("source_id", sa.String(length=128), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "calibration_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("git_sha", sa.String(length=40), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("f1_overall", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("f1_per_class", postgresql.JSONB(), nullable=False),
        sa.Column("n_surveys", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "llm_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cache_read_tokens", sa.Integer(), server_default="0"),
        sa.Column("cache_write_tokens", sa.Integer(), server_default="0"),
        sa.Column("cost_usd", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llmcalls_run_created", "llm_calls", ["run_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_llmcalls_run_created", table_name="llm_calls")
    op.drop_table("llm_calls")
    op.drop_table("calibration_runs")
    op.drop_table("calibration_surveys")
    op.drop_table("reports")
    op.drop_index("ix_probe_run_question", table_name="probe_responses")
    op.drop_table("probe_responses")
    op.drop_table("paraphrase_cache")
    op.drop_table("persona_pools")
    op.drop_index("ix_runs_survey_created", table_name="runs")
    op.drop_table("runs")
