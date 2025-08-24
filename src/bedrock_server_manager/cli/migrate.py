import click
import os
import questionary
from alembic.config import Config
from alembic import command
from importlib.resources import files

from ..config import bcm_config
from ..db.database import Database
from ..db import models
from ..config.const import env_name
from ..context import AppContext
from ..utils.migration import (
    migrate_env_vars_to_config_file,
    migrate_players_json_to_db,
    migrate_env_auth_to_db,
    migrate_env_token_to_db,
    migrate_json_configs_to_db,
    migrate_json_settings_to_db,
    migrate_services_to_db,
    migrate_global_theme_to_admin_user,
)


@click.group()
def migrate():
    """Database and settings migration tools."""
    pass


@migrate.command()
@click.pass_context
def database(ctx: click.Context):
    """Upgrades the database to the latest version."""
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
            raise click.Abort()

        # Now that env vars are migrated, load the AppContext
        app_context.load()

        try:
            click.echo("Migrating json settings to database...")
            migrate_json_settings_to_db(app_context)
        except Exception as e:
            click.echo(f"Failed to migrate json settings to database: {e}")
            raise click.Abort()

        try:
            click.echo("Migrating players.json to database...")
            migrate_players_json_to_db(app_context)
        except Exception as e:
            click.echo(f"Failed to migrate players.json: {e}")

        try:
            click.echo("Migrating environment auth settings to database...")
            migrate_env_auth_to_db(app_context)
        except Exception as e:
            click.echo(f"Failed to migrate environment auth settings: {e}")
            click.echo("Setup will be required after web server start.")

        try:
            click.echo("Migrating environment token settings to database...")
            migrate_env_token_to_db(app_context)
        except Exception as e:
            click.echo(f"Failed to migrate environment token settings: {e}")

        try:
            click.echo("Migrating global theme to admin user...")
            migrate_global_theme_to_admin_user(app_context)
        except Exception as e:
            click.echo(f"Failed to migrate global theme to admin user: {e}")

        try:
            click.echo("Migrating server and plugin configs to database...")
            migrate_json_configs_to_db(app_context)
        except Exception as e:
            click.echo(f"Failed to migrate server and plugin configs: {e}")

        try:
            click.echo("Migrating services to database...")
            migrate_services_to_db(app_context)
        except Exception as e:
            click.echo(f"Failed to migrate services: {e}")

        click.echo("Migration complete.")
    except Exception as e:
        click.echo(f"An error occurred during migrations: {e}")
        raise click.Abort()


@migrate.command(name="new-database")
@click.pass_context
def new_database(ctx: click.Context):
    """Migrates all data from the current database to a new database."""
    app_context: AppContext = ctx.obj["app_context"]
    source_db = app_context.db

    click.secho("Database Migration Utility", fg="cyan", bold=True)
    click.echo(
        "This utility will migrate all your data from the current database to a new one."
    )
    click.secho(
        "WARNING: This is a one-way operation. Make sure to have a backup of your current data.",
        fg="red",
    )

    if not questionary.confirm(
        "Are you sure you want to proceed?", default=False
    ).ask():
        click.secho("Operation cancelled.", fg="yellow")
        raise click.Abort()

    # Get destination database URL
    new_db_url = questionary.text(
        "Enter the full URL for the new database:",
        validate=lambda url: url.startswith(
            ("sqlite://", "postgresql://", "mysql://", "mariadb://")
        ),
        instruction="e.g., postgresql://user:pass@host/dbname",
    ).ask()

    if not new_db_url:
        click.secho("No database URL entered. Operation cancelled.", fg="yellow")
        raise click.Abort()

    click.echo(f"Migrating to new database at: {new_db_url}")

    # Create and initialize destination database
    dest_db = Database(db_url=new_db_url)
    try:
        dest_db.initialize()
        # Test connection and create tables
        with dest_db.session_manager() as db:
            click.echo(
                "Successfully connected to the destination database and created tables."
            )
    except Exception as e:
        click.secho(f"Failed to connect to the destination database: {e}", fg="red")
        raise click.Abort()

    # Define the order of migration to respect foreign key constraints
    MODELS_TO_MIGRATE = [
        models.User,
        models.Server,
        models.Setting,
        models.Plugin,
        models.RegistrationToken,
        models.Player,
        models.AuditLog,
    ]

    try:
        with source_db.session_manager() as source_session, dest_db.session_manager() as dest_session:
            for model in MODELS_TO_MIGRATE:
                model_name = model.__name__
                click.echo(f"Migrating table: {model_name}...")

                objects_to_migrate = source_session.query(model).all()

                if not objects_to_migrate:
                    click.echo(f"  No records to migrate for {model_name}.")
                    continue

                new_objects = []
                for obj in objects_to_migrate:
                    obj_data = {
                        c.name: getattr(obj, c.name) for c in obj.__table__.columns
                    }
                    new_objects.append(model(**obj_data))

                dest_session.bulk_save_objects(new_objects)
                click.echo(f"  Migrated {len(new_objects)} records for {model_name}.")

            dest_session.commit()
            click.secho("\nData migration successful!", fg="green")

    except Exception as e:
        click.secho(f"\nAn error occurred during data migration: {e}", fg="red", exc_info=True)
        click.secho(
            "Rolling back changes. The original database and configuration are untouched.",
            fg="yellow",
        )
        raise click.Abort()

    # Update the configuration
    try:
        click.echo("Updating configuration to use the new database...")
        bcm_config.set_config_value("db_url", new_db_url)
        click.secho("Configuration updated successfully.", fg="green")
        click.secho(
            "\nMigration complete! Please restart the application to apply the changes.",
            fg="cyan",
            bold=True,
        )
    except Exception as e:
        click.secho(f"Failed to update configuration file: {e}", fg="red")
        click.secho(
            f"Please manually update the 'db_url' in your config file to: {new_db_url}",
            fg="yellow",
        )
        raise click.Abort()
