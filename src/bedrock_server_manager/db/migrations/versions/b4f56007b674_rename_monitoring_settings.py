"""Rename monitoring settings

Revision ID: b4f56007b674
Revises: a85adea2863c
Create Date: 2026-05-26 06:40:08.714247

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4f56007b674"
down_revision: Union[str, Sequence[str], None] = "a85adea2863c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    # Rename SERVER_MONITORING_INTERVAL_SEC to monitoring.process_interval_sec
    connection.execute(
        sa.text(
            "UPDATE settings SET key = 'monitoring.process_interval_sec' WHERE key = 'SERVER_MONITORING_INTERVAL_SEC'"
        )
    )
    # Rename server_monitoring.player_log_monitoring_interval_sec to monitoring.player_interval_sec
    connection.execute(
        sa.text(
            "UPDATE settings SET key = 'monitoring.player_interval_sec' WHERE key = 'server_monitoring.player_log_monitoring_interval_sec'"
        )
    )
    # Remove the toggle
    connection.execute(
        sa.text(
            "DELETE FROM settings WHERE key = 'server_monitoring.player_log_monitoring_enabled'"
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    # Reverse renaming
    connection.execute(
        sa.text(
            "UPDATE settings SET key = 'SERVER_MONITORING_INTERVAL_SEC' WHERE key = 'monitoring.process_interval_sec'"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE settings SET key = 'server_monitoring.player_log_monitoring_interval_sec' WHERE key = 'monitoring.player_interval_sec'"
        )
    )
    # Note: we can't easily restore the deleted toggle value if it was user-modified, but we can insert the default.
    connection.execute(
        sa.text(
            "INSERT INTO settings (key, value) VALUES ('server_monitoring.player_log_monitoring_enabled', 'true')"
        )
    )
