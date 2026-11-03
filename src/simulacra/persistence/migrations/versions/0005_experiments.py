"""create experiment, treatment, trial and report tables

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("research_question", sa.Text(), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column(
            "population_version_id",
            sa.Integer(),
            sa.ForeignKey("population_versions.id"),
            nullable=False,
        ),
        sa.Column("scenario_json", sa.JSON(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
    )
    op.create_table(
        "treatments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "experiment_id",
            sa.Integer(),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("params_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_treatments_experiment_id", "treatments", ["experiment_id"])
    op.create_table(
        "trials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "run_id", sa.Integer(), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("persona_id", sa.String(), nullable=False),
        sa.Column("treatment_idx", sa.Integer(), nullable=False),
        sa.Column("repeat_idx", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("raw_output", sa.Text(), nullable=False),
        sa.Column("parsed_json", sa.JSON()),
        sa.Column("prompt_tokens", sa.Integer()),
        sa.Column("completion_tokens", sa.Integer()),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.UniqueConstraint("run_id", "persona_id", "treatment_idx", "repeat_idx"),
    )
    op.create_index("ix_trials_run_id", "trials", ["run_id"])
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "run_id", sa.Integer(), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("computed_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_reports_run_id", "reports", ["run_id"])


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_table("trials")
    op.drop_table("treatments")
    op.drop_table("experiments")
