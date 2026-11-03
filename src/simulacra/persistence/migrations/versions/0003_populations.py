"""create population tables

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "populations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "population_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "population_id",
            sa.Integer(),
            sa.ForeignKey("populations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("spec_json", sa.JSON(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("enrichment_json", sa.JSON(), nullable=False),
        sa.Column("diagnostics_json", sa.JSON()),
        sa.Column("progress_done", sa.Integer(), nullable=False),
        sa.Column("progress_total", sa.Integer(), nullable=False),
        sa.Column("error", sa.String()),
    )
    op.create_index(
        "ix_population_versions_population_id", "population_versions", ["population_id"]
    )
    op.create_table(
        "personas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "version_id",
            sa.Integer(),
            sa.ForeignKey("population_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("synthetic_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("attributes_json", sa.JSON(), nullable=False),
        sa.Column("bio", sa.Text(), nullable=False),
        sa.Column("extras_json", sa.JSON(), nullable=False),
        sa.Column("meta_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_personas_version_id", "personas", ["version_id"])


def downgrade() -> None:
    op.drop_table("personas")
    op.drop_table("population_versions")
    op.drop_table("populations")
