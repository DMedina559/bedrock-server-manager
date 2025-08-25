import click
import questionary
from alembic.config import Config
from alembic import command
from importlib.resources import files

from ..config import bcm_config
from ..db.database import Database
from ..db import models
from ..context import AppContext


@click.group()
def database():
    """Database management commands."""
    pass


import shutil
from datetime import datetime
from sqlalchemy import inspect


@database.command()
@click.pass_context
def upgrade(ctx: click.Context):
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
                message = (
                    "Unmanaged database detected."
                    if not is_managed
                    else "Database is not up to date."
                )
                click.secho(
                    f"{message} Stamping with the latest migration version...",
                    fg="yellow",
                )
                command.stamp(alembic_cfg, "head")
                click.secho("Database stamped successfully.", fg="green")

            # Upgrade Database
            click.echo("Running database upgrade...")
            command.upgrade(alembic_cfg, "head")
            click.echo("Database upgrade complete.")

        # --- Check for Admin User ---
        with app_context.db.session_manager() as db:
            admin_user = (
                db.query(models.User).filter(models.User.role == "admin").first()
            )
            if not admin_user:
                click.secho(
                    "\nWarning: No admin user found in the database.", fg="yellow"
                )
                click.echo(
                    "Please run the 'setup' command to create an initial admin user."
                )
                click.echo(
                    "Alternatively, you can manually create a user and assign the 'admin' role."
                )

    except Exception as e:
        click.secho(f"An error occurred during the database upgrade: {e}", fg="red")
        raise click.Abort()


@database.command(name="migrate")
@click.pass_context
def migrate_db(ctx: click.Context):
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
        with (
            source_db.session_manager() as source_session,
            dest_db.session_manager() as dest_session,
        ):
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
