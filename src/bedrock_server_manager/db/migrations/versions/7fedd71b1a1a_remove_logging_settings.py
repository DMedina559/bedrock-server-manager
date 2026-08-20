"""remove_logging_settings

Revision ID: 7fedd71b1a1a
Revises: b4f56007b674
Create Date: 2026-08-15 06:39:35.845432

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7fedd71b1a1a"
down_revision: Union[str, Sequence[str], None] = "b4f56007b674"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM settings WHERE key IN ('paths.logs', 'logging.level')")


def downgrade() -> None:
    # No downgrade path as settings are now managed in bcm_config
    pass
