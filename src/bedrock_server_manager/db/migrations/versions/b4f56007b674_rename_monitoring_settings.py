"""Rename monitoring settings

Revision ID: b4f56007b674
Revises: a85adea2863c
Create Date: 2026-05-26 06:40:08.714247

"""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4f56007b674"
down_revision: Union[str, Sequence[str], None] = "a85adea2863c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:  # noqa: C901
    connection = op.get_bind()

    old_process = connection.execute(
        sa.text(
            "SELECT value FROM settings WHERE `key` = 'SERVER_MONITORING_INTERVAL_SEC'"
        )
    ).scalar()

    old_server_monitoring = connection.execute(
        sa.text("SELECT value FROM settings WHERE `key` = 'server_monitoring'")
    ).scalar()

    process_interval = 10
    player_interval = 10

    if old_process is not None:
        try:
            if isinstance(old_process, str):
                process_interval = json.loads(old_process)
            else:
                process_interval = int(old_process)
        except (ValueError, TypeError, json.JSONDecodeError):
            pass

    if old_server_monitoring is not None:
        try:
            if isinstance(old_server_monitoring, str):
                data = json.loads(old_server_monitoring)
            else:
                data = old_server_monitoring
            if isinstance(data, dict):
                if "player_log_monitoring_interval_sec" in data:
                    player_interval = int(data["player_log_monitoring_interval_sec"])
        except (ValueError, TypeError, json.JSONDecodeError):
            pass

    new_monitoring = {
        "process_interval_sec": process_interval,
        "player_interval_sec": player_interval,
    }

    connection.execute(
        sa.text(
            "DELETE FROM settings WHERE `key` IN ('SERVER_MONITORING_INTERVAL_SEC', 'server_monitoring')"
        )
    )

    existing = connection.execute(
        sa.text("SELECT id FROM settings WHERE `key` = 'monitoring'")
    ).scalar()
    if existing:
        connection.execute(
            sa.text("UPDATE settings SET value = :val WHERE id = :id"),
            {"val": json.dumps(new_monitoring), "id": existing},
        )
    else:
        connection.execute(
            sa.text("INSERT INTO settings (`key`, value) VALUES ('monitoring', :val)"),
            {"val": json.dumps(new_monitoring)},
        )


def downgrade() -> None:
    connection = op.get_bind()

    # Get current monitoring setting
    current_monitoring = connection.execute(
        sa.text("SELECT value FROM settings WHERE `key` = 'monitoring'")
    ).scalar()

    process_interval = 10
    player_interval = 10

    if current_monitoring is not None:
        try:
            if isinstance(current_monitoring, str):
                data = json.loads(current_monitoring)
            else:
                data = current_monitoring
            if isinstance(data, dict):
                if "process_interval_sec" in data:
                    process_interval = int(data["process_interval_sec"])
                if "player_interval_sec" in data:
                    player_interval = int(data["player_interval_sec"])
        except (ValueError, TypeError, json.JSONDecodeError):
            pass

    # Delete new settings
    connection.execute(sa.text("DELETE FROM settings WHERE `key` = 'monitoring'"))

    # Restore old process interval
    connection.execute(
        sa.text(
            "INSERT INTO settings (`key`, value) VALUES ('SERVER_MONITORING_INTERVAL_SEC', :val)"
        ),
        {"val": json.dumps(process_interval)},
    )

    # Restore old server monitoring
    old_server_monitoring = {
        "player_log_monitoring_interval_sec": player_interval,
        "player_log_monitoring_enabled": True,
    }
    connection.execute(
        sa.text(
            "INSERT INTO settings (`key`, value) VALUES ('server_monitoring', :val)"
        ),
        {"val": json.dumps(old_server_monitoring)},
    )
