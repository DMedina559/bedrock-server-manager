"""Add application schedules and bounded execution history.

Revision ID: f72c401a908b
Revises: e4d63b721a90
"""

import sqlalchemy as sa
from alembic import op

revision = "f72c401a908b"
down_revision = "e4d63b721a90"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "schedules",
        sa.Column("schedule_id", sa.String(100), primary_key=True),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("legacy_server", sa.String(160), nullable=True),
    )
    op.create_table(
        "schedule_runs",
        sa.Column("run_id", sa.String(32), primary_key=True),
        sa.Column("schedule_id", sa.String(100), nullable=False),
        sa.Column("slot", sa.String(200), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("started_at", sa.String(40), nullable=False),
        sa.Column("finished_at", sa.String(40), nullable=True),
        sa.Column("correlation_id", sa.String(160), nullable=True),
        sa.Column("error", sa.String(300), nullable=True),
    )
    op.create_index("ix_schedule_runs_schedule_id", "schedule_runs", ["schedule_id"])
    op.create_index("ix_schedule_runs_started_at", "schedule_runs", ["started_at"])


def downgrade():
    op.drop_table("schedule_runs")
    op.drop_table("schedules")
