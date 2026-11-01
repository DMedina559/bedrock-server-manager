"""Persist verified login strength without inferring it from enrolled credentials.

Revision ID: h94a2c131f0b
Revises: g83c712e49a0
"""

import sqlalchemy as sa
from alembic import op

revision = "h94a2c131f0b"
down_revision = "g83c712e49a0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "login_sessions",
        sa.Column(
            "authentication_method",
            sa.String(32),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column(
        "login_sessions",
        sa.Column(
            "factor_verified", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade():
    with op.batch_alter_table("login_sessions") as batch:
        batch.drop_column("factor_verified")
        batch.drop_column("authentication_method")
