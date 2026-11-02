"""create benchmark tables

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "benchmark_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("hardware_json", sa.JSON(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("op", sa.String()),
        sa.Column("op_done", sa.Integer(), nullable=False),
        sa.Column("op_total", sa.Integer(), nullable=False),
        sa.Column("error", sa.String()),
    )
    op.create_table(
        "benchmark_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("benchmark_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_label", sa.String(), nullable=False),
        sa.Column("runtime_kind", sa.String(), nullable=False),
        sa.Column("base_url", sa.String(), nullable=False),
        sa.Column("runtime_version", sa.String()),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("model_digest", sa.String()),
        sa.Column("quantization", sa.String()),
        sa.Column("parameter_size", sa.String()),
        sa.Column("model_size_bytes", sa.Integer()),
        sa.Column("structured_mode", sa.String(), nullable=False),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("evidence", sa.String(), nullable=False),
        sa.Column("workload", sa.String(), nullable=False),
        sa.Column("concurrency", sa.Integer(), nullable=False),
        sa.Column("workload_hash", sa.String()),
        sa.Column("metrics_json", sa.JSON()),
        sa.Column("diagnostics_json", sa.JSON(), nullable=False),
        sa.Column("compat_json", sa.JSON()),
        sa.Column("extras_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_benchmark_results_run_id", "benchmark_results", ["run_id"])
    op.create_table(
        "benchmark_samples",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "result_id",
            sa.Integer(),
            sa.ForeignKey("benchmark_results.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("group", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("error", sa.String()),
        sa.Column("total_ms", sa.Float(), nullable=False),
        sa.Column("ttft_ms", sa.Float()),
        sa.Column("prompt_tokens", sa.Integer()),
        sa.Column("completion_tokens", sa.Integer()),
    )
    op.create_index("ix_benchmark_samples_result_id", "benchmark_samples", ["result_id"])
    op.create_table(
        "benchmark_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("benchmark_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
    )
    op.create_index("ix_benchmark_events_run_id", "benchmark_events", ["run_id"])


def downgrade() -> None:
    op.drop_table("benchmark_events")
    op.drop_table("benchmark_samples")
    op.drop_table("benchmark_results")
    op.drop_table("benchmark_runs")
