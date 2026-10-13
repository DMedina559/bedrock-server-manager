"""Add independent diagnostic history.

Revision ID: d1a602f43b71
Revises: c39b8e4271d0
"""

import sqlalchemy as sa
from alembic import op

revision = "d1a602f43b71"
down_revision = "c39b8e4271d0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "diagnostic_history",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("instance_id", sa.String(32), nullable=False),
        sa.Column("timestamp", sa.Float(), nullable=False),
        sa.Column("subsystem", sa.String(80), nullable=False),
        sa.Column("correlation_id", sa.String(160), nullable=True),
        sa.Column("record", sa.JSON(), nullable=False),
    )
    for field in ("instance_id", "timestamp", "subsystem", "correlation_id"):
        op.create_index(f"ix_diagnostic_history_{field}", "diagnostic_history", [field])


def downgrade():
    op.drop_table("diagnostic_history")
