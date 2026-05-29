"""Revamp Plugin schema with data migration

Revision ID: a85adea2863c
Revises: f2a7eb2d7c36
Create Date: 2026-05-26 04:30:44.244719

"""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = "a85adea2863c"
down_revision: Union[str, Sequence[str], None] = "f2a7eb2d7c36"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:  # noqa: C901
    # 1. Add new columns
    op.add_column(
        "plugins", sa.Column("enabled", sa.Boolean(), nullable=True, default=False)
    )
    op.add_column("plugins", sa.Column("version", sa.String(length=50), nullable=True))
    op.add_column("plugins", sa.Column("author", sa.String(length=255), nullable=True))
    op.add_column("plugins", sa.Column("description", sa.Text(), nullable=True))

    op.add_column(
        "servers",
        sa.Column(
            "installed_version",
            sa.String(length=50),
            nullable=True,
            server_default="UNKNOWN",
        ),
    )
    op.add_column(
        "servers",
        sa.Column(
            "status", sa.String(length=50), nullable=True, server_default="UNKNOWN"
        ),
    )
    op.add_column(
        "servers",
        sa.Column(
            "autoupdate", sa.Boolean(), nullable=True, server_default=sa.text("0")
        ),
    )
    op.add_column(
        "servers",
        sa.Column(
            "autostart", sa.Boolean(), nullable=True, server_default=sa.text("0")
        ),
    )
    op.add_column(
        "servers",
        sa.Column(
            "target_version",
            sa.String(length=50),
            nullable=True,
            server_default="UNKNOWN",
        ),
    )
    op.add_column("servers", sa.Column("custom", sa.JSON(), nullable=True))

    connection = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(connection)

    # If the server_bans table was already created by create_all(), drop it first.
    if inspector.has_table("server_bans"):
        # We need to drop indices before dropping the table if it exists.
        # But SQLite drop table handles indices too.
        op.drop_table("server_bans")

    op.create_table(
        "server_bans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("server_id", sa.Integer(), nullable=True),
        sa.Column("player_name", sa.String(length=80), nullable=True),
        sa.Column("xuid", sa.String(length=20), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("banned_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["server_id"],
            ["servers.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("server_bans", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_server_bans_id"), ["id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_server_bans_player_name"), ["player_name"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_server_bans_server_id"), ["server_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_server_bans_xuid"), ["xuid"], unique=False)

    # 2. Migrate data
    connection = op.get_bind()

    # Read existing plugins
    result = connection.execute(sa.text("SELECT id, config FROM plugins")).fetchall()
    for row in result:
        plugin_id = row[0]
        config_data = row[1]

        # Determine values from existing JSON if it exists
        enabled = False
        version = None
        author = None
        description = None

        if config_data:
            if isinstance(config_data, str):
                try:
                    config_data = json.loads(config_data)
                except Exception:
                    config_data = {}
            if isinstance(config_data, dict):
                enabled = bool(config_data.get("enabled", False))
                version = config_data.get("version")
                author = config_data.get("author")
                description = config_data.get("description")

        connection.execute(
            sa.text(
                "UPDATE plugins SET enabled = :enabled, version = :version, author = :author, description = :description WHERE id = :id"
            ),
            {
                "enabled": enabled,
                "version": version,
                "author": author,
                "description": description,
                "id": plugin_id,
            },
        )

    # Read existing servers
    server_result = connection.execute(
        sa.text("SELECT id, config FROM servers")
    ).fetchall()
    for row in server_result:
        server_id = row[0]
        config_data = row[1]

        installed_version = "UNKNOWN"
        status = "UNKNOWN"
        autoupdate = False
        autostart = False
        target_version = "UNKNOWN"
        custom = {}

        if config_data:
            if isinstance(config_data, str):
                try:
                    config_data = json.loads(config_data)
                except Exception:
                    config_data = {}
            if isinstance(config_data, dict):
                server_info = config_data.get("server_info", {})
                settings = config_data.get("settings", {})

                installed_version = server_info.get("installed_version", "UNKNOWN")
                status = server_info.get("status", "UNKNOWN")
                autoupdate = bool(settings.get("autoupdate", False))
                autostart = bool(settings.get("autostart", False))
                target_version = settings.get("target_version", "UNKNOWN")
                custom = config_data.get("custom", {})

        connection.execute(
            sa.text(
                "UPDATE servers SET installed_version = :installed_version, status = :status, autoupdate = :autoupdate, autostart = :autostart, target_version = :target_version, custom = :custom WHERE id = :id"
            ),
            {
                "installed_version": installed_version,
                "status": status,
                "autoupdate": autoupdate,
                "autostart": autostart,
                "target_version": target_version,
                "custom": json.dumps(custom),
                "id": server_id,
            },
        )

    # 3. Drop config columns
    with op.batch_alter_table("plugins", schema=None) as batch_op:
        batch_op.drop_column("config")

    with op.batch_alter_table("servers", schema=None) as batch_op:
        batch_op.drop_column("config")

    # Drop server_id from settings
    # We must explicitly drop the foreign key constraint first for MariaDB/MySQL
    connection = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(connection)
    fks = inspector.get_foreign_keys("settings")
    fk_name = None
    for fk in fks:
        if "server_id" in fk["constrained_columns"]:
            fk_name = fk["name"]
            break

    indices = inspector.get_indexes("settings")
    index_name = None
    for idx in indices:
        if "server_id" in idx["column_names"]:
            index_name = idx["name"]
            break

    with op.batch_alter_table("settings", schema=None) as batch_op:
        if fk_name:
            batch_op.drop_constraint(fk_name, type_="foreignkey")
        if index_name:
            batch_op.drop_index(index_name)
        batch_op.drop_column("server_id")


def downgrade() -> None:
    # 1. Add config columns back
    op.add_column("plugins", sa.Column("config", sqlite.JSON(), nullable=True))
    op.add_column("servers", sa.Column("config", sqlite.JSON(), nullable=True))
    op.add_column("settings", sa.Column("server_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_settings_server_id_servers", "servers", ["server_id"], ["id"]
        )

    # 2. Migrate data back
    connection = op.get_bind()

    # Migrate plugins
    result = connection.execute(
        sa.text("SELECT id, enabled, version, author, description FROM plugins")
    ).fetchall()
    for row in result:
        plugin_id = row[0]
        enabled = bool(row[1])
        version = row[2]
        author = row[3]
        description = row[4]

        config_data = {
            "enabled": enabled,
            "version": version,
            "author": author,
            "description": description,
        }

        connection.execute(
            sa.text("UPDATE plugins SET config = :config WHERE id = :id"),
            {"config": json.dumps(config_data), "id": plugin_id},
        )

    # Migrate servers
    server_result = connection.execute(
        sa.text(
            "SELECT id, installed_version, status, autoupdate, autostart, target_version, custom FROM servers"
        )
    ).fetchall()
    for row in server_result:
        server_id = row[0]
        installed_version = row[1]
        status = row[2]
        autoupdate = bool(row[3])
        autostart = bool(row[4])
        target_version = row[5]
        custom_data = row[6]

        if custom_data and isinstance(custom_data, str):
            try:
                custom_data = json.loads(custom_data)
            except Exception:
                custom_data = {}
        if not isinstance(custom_data, dict):
            custom_data = {}

        config_data = {
            "config_schema_version": 2,
            "server_info": {"installed_version": installed_version, "status": status},
            "settings": {
                "autoupdate": autoupdate,
                "autostart": autostart,
                "target_version": target_version,
            },
            "custom": custom_data,
        }

        connection.execute(
            sa.text("UPDATE servers SET config = :config WHERE id = :id"),
            {"config": json.dumps(config_data), "id": server_id},
        )

    # 3. Drop new columns and tables
    op.drop_table("server_bans")

    with op.batch_alter_table("plugins", schema=None) as batch_op:
        batch_op.drop_column("description")
        batch_op.drop_column("author")
        batch_op.drop_column("version")
        batch_op.drop_column("enabled")

    with op.batch_alter_table("servers", schema=None) as batch_op:
        batch_op.drop_column("custom")
        batch_op.drop_column("target_version")
        batch_op.drop_column("autostart")
        batch_op.drop_column("autoupdate")
        batch_op.drop_column("status")
        batch_op.drop_column("installed_version")
