"""Move plugin configuration out of global settings.

Revision ID: c39b8e4271d0
Revises: 7fedd71b1a1a
"""

import sqlalchemy as sa
from alembic import op

revision = "c39b8e4271d0"
down_revision = "7fedd71b1a1a"
branch_labels = None
depends_on = None


def _tables():
    settings = sa.table(
        "settings",
        sa.column("id", sa.Integer),
        sa.column("key", sa.String),
        sa.column("value", sa.JSON),
    )
    plugins = sa.table(
        "plugin_settings",
        sa.column("plugin_name", sa.String),
        sa.column("settings", sa.JSON),
    )
    return settings, plugins


def _merge(target, source):
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge(target[key], value)
        else:
            target[key] = value


def upgrade():
    connection = op.get_bind()
    settings, plugins = _tables()
    rows = (
        connection.execute(sa.select(settings).order_by(settings.c.id)).mappings().all()
    )
    values = {}
    ids = []
    for row in rows:
        key = row["key"]
        if key != "plugin_settings" and not (
            isinstance(key, str) and key.startswith("plugin_settings.")
        ):
            continue
        ids.append(row["id"])
        if key == "plugin_settings":
            if not isinstance(row["value"], dict):
                raise ValueError("Plugin settings must be a JSON object")
            _merge(values, row["value"])
        else:
            parts = key.split(".")[1:]
            target = values
            for part in parts[:-1]:
                target = target.setdefault(part, {})
                if not isinstance(target, dict):
                    raise ValueError("Conflicting legacy plugin settings paths")
            target[parts[-1]] = row["value"]
    if any(not isinstance(value, dict) for value in values.values()):
        raise ValueError("Each plugin's settings must be a JSON object")
    op.create_table(
        "plugin_settings",
        sa.Column("plugin_name", sa.String(255), primary_key=True),
        sa.Column("settings", sa.JSON(), nullable=False),
    )
    if values:
        connection.execute(
            plugins.insert(),
            [
                {"plugin_name": name, "settings": value}
                for name, value in values.items()
            ],
        )
    if ids:
        connection.execute(settings.delete().where(settings.c.id.in_(ids)))


def downgrade():
    connection = op.get_bind()
    settings, plugins = _tables()
    values = {
        row.plugin_name: row.settings for row in connection.execute(sa.select(plugins))
    }
    connection.execute(settings.delete().where(settings.c.key == "plugin_settings"))
    connection.execute(settings.insert().values(key="plugin_settings", value=values))
    op.drop_table("plugin_settings")
