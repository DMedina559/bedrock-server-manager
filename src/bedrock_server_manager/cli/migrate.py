import click
import os
from alembic.config import Config
from alembic import command
from importlib.resources import files

from ..config.const import env_name
from ..context import AppContext
from ..utils.migration import (
    migrate_env_vars_to_config_file,
    migrate_players_json_to_db,
    migrate_env_auth_to_db,
    migrate_env_token_to_db,
)


@click.group()
def migrate():
    """Database and settings migration tools."""
    pass


@migrate.command()
@click.pass_context
def database(ctx: click.Context):
    """Upgrades the database to the latest version."""
    app_context: AppContext = ctx.obj["app_context"]
    app_context.load()
    try:
        click.echo("Upgrading database...")
        alembic_ini_path = files("bedrock_server_manager").joinpath("db/alembic.ini")
        alembic_cfg = Config(str(alembic_ini_path))
        command.upgrade(alembic_cfg, "head")
        click.echo("Database upgrade complete.")
    except Exception as e:
        click.echo(f"An error occurred during the database upgrade: {e}")
        raise click.Abort()


@migrate.command()
@click.pass_context
def old_config(ctx: click.Context):
    """Migrates settings from environment variables and old formats to the database."""
    app_context: AppContext = ctx.obj["app_context"]
    try:
        try:
            click.echo("Migrating environment variables to config file...")
            migrate_env_vars_to_config_file()
        except Exception as e:
            click.echo(f"Failed to migrate environment variables to config file: {e}")

        # Now that env vars are migrated, load the AppContext
        app_context.load()

        settings = app_context.settings

        try:
            click.echo("Migrating players.json to database...")
            players_json_path = os.path.join(settings.config_dir, "players.json")
            migrate_players_json_to_db(players_json_path)
        except Exception as e:
            click.echo(f"Failed to migrate players.json: {e}")

        try:
            click.echo("Migrating environment auth settings to database...")
            migrate_env_auth_to_db(env_name)
        except Exception as e:
            click.echo(f"Failed to migrate environment auth settings: {e}")

        try:
            click.echo("Migrating environment token settings to database...")
            migrate_env_token_to_db(env_name)
        except Exception as e:
            click.echo(f"Failed to migrate environment token settings: {e}")

        click.echo("Migration complete.")
    except Exception as e:
        click.echo(f"An error occurred during settings migration: {e}")
        raise click.Abort()
