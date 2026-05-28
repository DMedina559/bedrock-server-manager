import shutil
from datetime import datetime
from importlib.resources import files
from typing import Any

import click
import questionary
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from ..config import bcm_config
from ..context import AppContext
from ..db import models
from ..db.database import Database


@click.group()
def database():
    """Database management commands."""
    pass


@database.command()
@click.pass_context
def upgrade(ctx: click.Context):  # noqa: C901
    """Upgrades the database to the latest version, stamping it if necessary."""
    app_context: AppContext = ctx.obj["app_context"]
    alembic_ini_path = files("bedrock_server_manager").joinpath("db/alembic.ini")
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("skip_logging_config", "true")

    # --- Backup Database ---
    db_url = app_context.db.get_database_url()
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    if db_url.startswith("sqlite:///"):
        db_path = db_url.split("sqlite:///")[1]
        backup_dir = app_context.settings.get("paths.backups")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{backup_dir}/db_backup_{timestamp}.sqlite3"
        try:
            shutil.copy(db_path, backup_path)
            click.secho(f"Database backed up to {backup_path}", fg="green")
        except Exception as e:
            click.secho(f"Failed to create database backup: {e}", fg="red")
            if not click.confirm(
                "Do you want to continue without a backup?", default=False
            ):
                raise click.Abort()
    else:
        click.secho(
            "Your database is not SQLite. Please make sure you have a backup before proceeding.",
            fg="yellow",
        )
        if not click.confirm("Do you want to continue?", default=False):
            raise click.Abort()

    # --- Run Migrations ---
    try:
        engine = app_context.db.engine
        if engine is None:
            raise click.Abort("Database engine is not available.")

        with engine.begin() as connection:
            alembic_cfg.attributes["connection"] = connection

            # Check if the database is at the latest revision. If not, stamp it.
            # This handles both missing alembic_version table and empty table cases.
            inspector = inspect(connection)
            is_managed = inspector.has_table("alembic_version")
            current_rev = None
            if is_managed:
                from sqlalchemy import text

                current_rev = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one_or_none()

            if not is_managed or not current_rev:
                # Detect if the database has old columns or not.
                has_config_column = False
                if inspector.has_table("plugins"):
                    columns = [c["name"] for c in inspector.get_columns("plugins")]
                    has_config_column = "config" in columns

                message = (
                    "Unmanaged database detected."
                    if not is_managed
                    else "Database is missing revision hash."
                )

                if has_config_column:
                    click.secho(
                        f"{message} Stamping with the baseline migration version...",
                        fg="yellow",
                    )
                    # Stamp with the initial schema baseline so subsequent migrations can run
                    command.stamp(alembic_cfg, "f2a7eb2d7c36")
                    click.secho("Database stamped with baseline.", fg="green")
                else:
                    click.secho(
                        f"{message} Brand new database detected. Stamping with latest version...",
                        fg="yellow",
                    )
                    # Stamp with the latest migration since create_all() already created it
                    command.stamp(alembic_cfg, "head")
                    click.secho("Database stamped with latest.", fg="green")

            # Upgrade Database
            click.echo("Running database upgrade...")
            command.upgrade(alembic_cfg, "head")
            click.echo("Database upgrade complete.")

        # --- Check for Admin User ---
        with app_context.db.session_manager() as db:  # type: ignore
            admin_user = (
                db.query(models.User).filter(models.User.role == "admin").first()
            )
            if not admin_user:
                click.secho(
                    "\nWarning: No admin user found in the database.", fg="yellow"
                )
                click.echo("Please run the web server to create an initial admin user.")

    except Exception as e:
        click.secho(f"An error occurred during the database upgrade: {e}", fg="red")
        raise click.Abort()


@database.command()
@click.option(
    "--revision",
    "-r",
    default="-1",
    help="The revision to downgrade to (e.g., -1 for previous, or a specific revision ID).",
)
@click.pass_context
def downgrade(ctx: click.Context, revision: str):
    """Downgrades the database to a previous version."""
    app_context: AppContext = ctx.obj["app_context"]
    alembic_ini_path = files("bedrock_server_manager").joinpath("db/alembic.ini")
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("skip_logging_config", "true")

    db_url = app_context.db.get_database_url()
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    click.secho(
        f"WARNING: Downgrading the database can lead to data loss.",
        fg="yellow",
        bold=True,
    )
    if not click.confirm("Are you sure you want to proceed?", default=False):
        raise click.Abort()

    # --- Backup Database ---
    if db_url.startswith("sqlite:///"):
        db_path = db_url.split("sqlite:///")[1]
        backup_dir = app_context.settings.get("paths.backups")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{backup_dir}/db_backup_pre_downgrade_{timestamp}.sqlite3"
        try:
            shutil.copy(db_path, backup_path)
            click.secho(f"Database backed up to {backup_path}", fg="green")
        except Exception as e:
            click.secho(f"Failed to create database backup: {e}", fg="red")
            if not click.confirm(
                "Do you want to continue without a backup?", default=False
            ):
                raise click.Abort()

    try:
        engine = app_context.db.engine
        if engine is None:
            raise click.Abort("Database engine is not available.")

        with engine.begin() as connection:
            alembic_cfg.attributes["connection"] = connection
            click.echo(f"Running database downgrade to revision: {revision}...")
            command.downgrade(alembic_cfg, revision)
            click.echo("Database downgrade complete.")

    except Exception as e:
        click.secho(f"An error occurred during the database downgrade: {e}", fg="red")
        raise click.Abort()


@database.command(name="migrate")
@click.pass_context
def migrate_db(ctx: click.Context):  # noqa: C901
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
        with dest_db.session_manager():
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
        with (
            source_db.session_manager() as source_session,  # type: ignore
            dest_db.session_manager() as dest_session,  # type: ignore
        ):
            for model in MODELS_TO_MIGRATE:
                model_name = model.__name__
                click.echo(f"Migrating table: {model_name}...")

                objects_to_migrate: Any = source_session.query(model).all()

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
        click.secho(
            f"\nAn error occurred during data migration: {e}", fg="red", exc_info=True
        )
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
