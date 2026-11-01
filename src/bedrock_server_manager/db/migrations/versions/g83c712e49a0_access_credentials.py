"""Add access identities, sessions, MFA, trusted devices, passkeys, and invitation digests.

Revision ID: g83c712e49a0
Revises: f72c401a908b
"""

import hashlib
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "g83c712e49a0"
down_revision = "f72c401a908b"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()

    # 1. Add immutable access_id to users and servers (plus auth_revision on users)
    op.add_column(
        "users",
        sa.Column("auth_revision", sa.Integer(), nullable=False, server_default="0"),
    )
    for table in ("users", "servers"):
        op.add_column(table, sa.Column("access_id", sa.String(32), nullable=True))
        rows = connection.execute(sa.text(f"SELECT id FROM {table}")).fetchall()
        for row in rows:
            connection.execute(
                sa.text(f"UPDATE {table} SET access_id=:identity WHERE id=:id"),
                {"identity": uuid4().hex, "id": row[0]},
            )
        with op.batch_alter_table(table) as batch:
            batch.alter_column("access_id", existing_type=sa.String(32), nullable=False)
            batch.create_unique_constraint(f"uq_{table}_access_id", ["access_id"])

    # 2. Migrate registration_tokens from plaintext token to SHA-256 token_digest
    with op.batch_alter_table("registration_tokens") as batch:
        batch.add_column(sa.Column("token_digest", sa.String(64), nullable=True))

    rows = connection.execute(
        sa.text("SELECT id, token FROM registration_tokens WHERE token IS NOT NULL")
    ).fetchall()
    for row_id, raw_token in rows:
        digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        connection.execute(
            sa.text(
                "UPDATE registration_tokens SET token_digest = :digest WHERE id = :id"
            ),
            {"digest": digest, "id": row_id},
        )
    connection.execute(
        sa.text("DELETE FROM registration_tokens WHERE token_digest IS NULL")
    )
    with op.batch_alter_table("registration_tokens") as batch:
        batch.alter_column("token_digest", existing_type=sa.String(64), nullable=False)
        batch.create_index(
            "ix_registration_tokens_token_digest", ["token_digest"], unique=True
        )
        batch.drop_index("ix_registration_tokens_token")
        batch.drop_column("token")

    # 3. Access grants and integration tokens
    op.create_table(
        "access_revision",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
    )
    connection.execute(
        sa.text("INSERT INTO access_revision (id, revision) VALUES (1, 0)")
    )
    op.create_table(
        "account_server_access",
        sa.Column("owner_id", sa.String(32), primary_key=True),
        sa.Column("assigned_only", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "server_access_grants",
        sa.Column("owner_id", sa.String(32), primary_key=True),
        sa.Column("server_id", sa.String(32), primary_key=True),
        sa.Column("permissions", sa.JSON(), nullable=False),
    )
    op.create_table(
        "integration_tokens",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("owner_id", sa.String(32), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("server_ids", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=True),
        sa.Column("last_used_at", sa.Integer(), nullable=True),
        sa.Column("revoked_at", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_integration_tokens_owner_id", "integration_tokens", ["owner_id"]
    )

    # 4. Login sessions, account security, throttling, and security events
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
        sa.Column("verified_device_id", sa.String(32), nullable=True),
        sa.Column(
            "authentication_method",
            sa.String(32),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column(
            "factor_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
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

    # 5. Trusted devices
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

    # 6. Passkey credentials and single-use challenges
    op.create_table(
        "passkey_credentials",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("owner_id", sa.String(32), nullable=False),
        sa.Column("credential_id", sa.String(1400), nullable=False, unique=True),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("sign_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("transports", sa.JSON(), nullable=False),
        sa.Column("aaguid", sa.String(64), nullable=True),
        sa.Column(
            "user_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "backup_eligible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "backup_state",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("last_used_at", sa.Integer(), nullable=True),
        sa.Column("revoked_at", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_passkey_credentials_owner_id", "passkey_credentials", ["owner_id"]
    )
    op.create_index(
        "ix_passkey_credentials_credential_id",
        "passkey_credentials",
        ["credential_id"],
        unique=True,
    )

    op.create_table(
        "passkey_challenges",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("owner_id", sa.String(32), nullable=True),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("challenge", sa.String(128), nullable=False, unique=True),
        sa.Column("rp_id", sa.String(255), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_passkey_challenges_owner_id", "passkey_challenges", ["owner_id"]
    )
    op.create_index(
        "ix_passkey_challenges_expires_at", "passkey_challenges", ["expires_at"]
    )


def downgrade():
    for table in (
        "passkey_challenges",
        "passkey_credentials",
        "trusted_devices",
        "auth_security_events",
        "auth_throttle",
        "account_security",
        "login_sessions",
        "integration_tokens",
        "server_access_grants",
        "account_server_access",
        "access_revision",
    ):
        op.drop_table(table)

    # One-way SHA-256 digests cannot be reversed to plaintext tokens on downgrade.
    with op.batch_alter_table("registration_tokens") as batch:
        batch.add_column(sa.Column("token", sa.String(255), nullable=True))
        batch.drop_index("ix_registration_tokens_token_digest")
        batch.create_index("ix_registration_tokens_token", ["token"], unique=True)
        batch.drop_column("token_digest")

    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("uq_users_access_id", type_="unique")
        batch.drop_column("access_id")
        batch.drop_column("auth_revision")

    with op.batch_alter_table("servers") as batch:
        batch.drop_constraint("uq_servers_access_id", type_="unique")
        batch.drop_column("access_id")
