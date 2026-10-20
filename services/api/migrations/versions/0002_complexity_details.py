"""Add structured complexity measurement details."""

from alembic import op
import sqlalchemy as sa


revision = "0002_complexity_details"
down_revision = "0001_jobs_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "complexity_results",
        sa.Column("details", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("complexity_results", "details")
