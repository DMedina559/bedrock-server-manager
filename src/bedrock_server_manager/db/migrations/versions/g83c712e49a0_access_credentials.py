"""Add immutable access identities, server grants and integration credentials.

Revision ID: g83c712e49a0
Revises: f72c401a908b
"""

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "g83c712e49a0"
down_revision = "f72c401a908b"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
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
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.Column("last_used_at", sa.Integer(), nullable=True),
        sa.Column("revoked_at", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_integration_tokens_owner_id", "integration_tokens", ["owner_id"]
    )


def downgrade():
    for table in (
        "integration_tokens",
        "server_access_grants",
        "account_server_access",
        "access_revision",
    ):
        op.drop_table(table)
    for table in ("users", "servers"):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(f"uq_{table}_access_id", type_="unique")
            batch.drop_column("access_id")
