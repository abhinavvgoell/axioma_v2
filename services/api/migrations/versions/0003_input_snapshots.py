"""Persist immutable job input snapshots for exact benchmark replay."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_input_snapshots"
down_revision: Union[str, None] = "0002_complexity_details"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "input_snapshots",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "job_id",
            sa.String(length=36),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_snapshot_id",
            sa.String(length=36),
            sa.ForeignKey("input_snapshots.id", ondelete="SET NULL"),
        ),
        sa.Column("snapshot_key", sa.String(length=160), nullable=False),
        sa.Column("origin", sa.String(length=32), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("problem_pack_identity", sa.JSON()),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("input_sha256", sa.String(length=64), nullable=False),
        sa.Column("generator_version", sa.String(length=80)),
        sa.Column("generator_artifact_sha256", sa.String(length=64)),
        sa.Column("seed", sa.Integer()),
        sa.Column("size_path", sa.String(length=120)),
        sa.Column("strategy", sa.String(length=80)),
        sa.Column("runtime_configuration", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id", "snapshot_key", name="uq_input_snapshot_job_key"),
    )
    op.create_index(
        "ix_input_snapshots_job_origin", "input_snapshots", ["job_id", "origin"]
    )


def downgrade() -> None:
    op.drop_index("ix_input_snapshots_job_origin", table_name="input_snapshots")
    op.drop_table("input_snapshots")
