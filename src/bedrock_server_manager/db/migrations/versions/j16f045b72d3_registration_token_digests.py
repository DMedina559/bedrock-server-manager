"""Store registration tokens as SHA-256 digests.

Revision ID: j16f045b72d3
Revises: i05e934a61c2
"""

import hashlib

import sqlalchemy as sa
from alembic import op

revision = "j16f045b72d3"
down_revision = "i05e934a61c2"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()

    # 1. Add nullable token_digest column
    with op.batch_alter_table("registration_tokens") as batch:
        batch.add_column(sa.Column("token_digest", sa.String(64), nullable=True))

    # 2. Migrate existing plaintext tokens to SHA-256 digests
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

    # 3. Remove rows with null digests
    connection.execute(
        sa.text("DELETE FROM registration_tokens WHERE token_digest IS NULL")
    )

    # 4. Enforce NOT NULL, unique constraint, index, and drop plaintext token
    with op.batch_alter_table("registration_tokens") as batch:
        batch.alter_column("token_digest", existing_type=sa.String(64), nullable=False)
        batch.create_unique_constraint(
            "uq_registration_tokens_token_digest", ["token_digest"]
        )
        batch.create_index("ix_registration_tokens_token_digest", ["token_digest"])
        batch.drop_index("ix_registration_tokens_token")
        batch.drop_column("token")


def downgrade():
    # One-way SHA-256 digests cannot be reversed to plaintext tokens on downgrade.
    # Existing tokens cannot be restored to plaintext.
    with op.batch_alter_table("registration_tokens") as batch:
        batch.add_column(sa.Column("token", sa.String(255), nullable=True))
        batch.drop_constraint("uq_registration_tokens_token_digest", type_="unique")
        batch.drop_index("ix_registration_tokens_token_digest")
        batch.create_index("ix_registration_tokens_token", ["token"], unique=True)
        batch.drop_column("token_digest")
