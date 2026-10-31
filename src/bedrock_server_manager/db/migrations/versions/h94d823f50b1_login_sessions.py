"""Track revocable login families, MFA enrollment and authentication budgets."""

import sqlalchemy as sa
from alembic import op

revision = "h94d823f50b1"
down_revision = "g83c712e49a0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("auth_revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "login_sessions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("owner_id", sa.String(32), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("user_agent", sa.String(512), nullable=False),
        sa.Column("ip_address", sa.String(64), nullable=False),
        *[
            sa.Column(name, sa.Integer(), nullable=False)
            for name in ("created_at", "last_seen_at", "expires_at", "verified_at")
        ],
        sa.Column("revoked_at", sa.Integer(), nullable=True),
    )
    op.create_index("ix_login_sessions_owner_id", "login_sessions", ["owner_id"])
    op.create_table(
        "account_security",
        sa.Column("owner_id", sa.String(32), primary_key=True),
        sa.Column("totp_secret", sa.Text(), nullable=True),
        sa.Column("pending_secret", sa.Text(), nullable=True),
        sa.Column("pending_until", sa.Integer(), nullable=True),
        sa.Column("last_counter", sa.Integer(), nullable=False),
        sa.Column("recovery_hashes", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_table(
        "auth_throttle",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("window", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )

    op.create_table(
        "auth_security_events",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("owner_id", sa.String(32), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("timestamp", sa.Integer(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_auth_security_events_owner_id", "auth_security_events", ["owner_id"]
    )


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_column("auth_revision")
    for table in (
        "auth_security_events",
        "auth_throttle",
        "account_security",
        "login_sessions",
    ):
        op.drop_table(table)
