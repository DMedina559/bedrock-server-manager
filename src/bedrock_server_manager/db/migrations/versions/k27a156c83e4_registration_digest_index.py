"""Align the registration digest index with the ORM metadata.

Revision ID: k27a156c83e4
Revises: j16f045b72d3
"""

from alembic import op

revision = "k27a156c83e4"
down_revision = "j16f045b72d3"
branch_labels = None
depends_on = None


def upgrade():
    # A follow-up also repairs databases that already applied the digest migration.
    with op.batch_alter_table("registration_tokens") as batch:
        batch.drop_constraint("uq_registration_tokens_token_digest", type_="unique")
        batch.drop_index("ix_registration_tokens_token_digest")
        batch.create_index(
            "ix_registration_tokens_token_digest", ["token_digest"], unique=True
        )


def downgrade():
    with op.batch_alter_table("registration_tokens") as batch:
        batch.drop_index("ix_registration_tokens_token_digest")
        batch.create_unique_constraint(
            "uq_registration_tokens_token_digest", ["token_digest"]
        )
        batch.create_index("ix_registration_tokens_token_digest", ["token_digest"])
