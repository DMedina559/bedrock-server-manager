"""Allow integration credentials without an expiration deadline."""

import time

import sqlalchemy as sa
from alembic import op

revision = "i05e934a61c2"
down_revision = "h94d823f50b1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("integration_tokens") as batch:
        batch.alter_column("expires_at", existing_type=sa.Integer(), nullable=True)


def downgrade():
    # Older releases cannot represent non-expiring credentials. Expire those
    # credentials on downgrade rather than silently extending their authority.
    tokens = sa.table("integration_tokens", sa.column("expires_at", sa.Integer()))
    op.execute(
        tokens.update()
        .where(tokens.c.expires_at.is_(None))
        .values(expires_at=int(time.time()))
    )
    with op.batch_alter_table("integration_tokens") as batch:
        batch.alter_column("expires_at", existing_type=sa.Integer(), nullable=False)
