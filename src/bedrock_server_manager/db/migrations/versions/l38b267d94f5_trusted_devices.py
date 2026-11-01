"""Persist revocable, finite remembered-device second-factor credentials.

Revision ID: l38b267d94f5
Revises: k27a156c83e4
"""

import sqlalchemy as sa
from alembic import op

revision = "l38b267d94f5"
down_revision = "k27a156c83e4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("login_sessions") as batch:
        batch.add_column(sa.Column("verified_device_id", sa.String(32), nullable=True))
    op.create_table(
        "trusted_devices",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("owner_id", sa.String(32), nullable=False),
        sa.Column("token_digest", sa.String(64), nullable=False),
        sa.Column("auth_revision", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("user_agent", sa.String(512), nullable=False),
        sa.Column("ip_address", sa.String(64), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("last_used_at", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.Column("revoked_at", sa.Integer(), nullable=True),
    )
    op.create_index("ix_trusted_devices_owner_id", "trusted_devices", ["owner_id"])
    op.create_index("ix_trusted_devices_expires_at", "trusted_devices", ["expires_at"])


def downgrade():
    # Old versions cannot interpret remembered-device verification provenance.
    op.execute(
        "UPDATE login_sessions SET verified_at = 0 WHERE verified_device_id IS NOT NULL"
    )
    with op.batch_alter_table("login_sessions") as batch:
        batch.drop_column("verified_device_id")
    op.drop_index("ix_trusted_devices_expires_at", table_name="trusted_devices")
    op.drop_index("ix_trusted_devices_owner_id", table_name="trusted_devices")
    op.drop_table("trusted_devices")
