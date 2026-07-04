import json
import shutil
from datetime import datetime
from importlib.resources import files

import click
import questionary
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from ..context import AppContext
from ..db import models


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
                message = (
                    "Unmanaged database detected."
                    if not is_managed
                    else "Database is missing revision hash."
                )

                # Detect if the database has old columns or not.
                has_config_column = False
                if inspector.has_table("plugins"):
                    columns = [c["name"] for c in inspector.get_columns("plugins")]
                    if "config" in columns:
                        has_config_column = True
                if inspector.has_table("servers") and not has_config_column:
                    columns = [c["name"] for c in inspector.get_columns("servers")]
                    if "config" in columns:
                        has_config_column = True

                if has_config_column:
                    click.secho(
                        f"{message} Stamping with the baseline migration version...",
                        fg="yellow",
                    )
                    # Stamp with the initial schema baseline so subsequent migrations can run
                    if is_managed:
                        from sqlalchemy import text

                        connection.execute(text("DELETE FROM alembic_version"))
                        connection.execute(
                            text(
                                "INSERT INTO alembic_version (version_num) VALUES ('f2a7eb2d7c36')"
                            )
                        )
                    else:
                        command.stamp(alembic_cfg, "f2a7eb2d7c36")
                    click.secho("Database stamped with baseline.", fg="green")
                elif inspector.has_table("server_bans") or inspector.has_table("users"):
                    click.secho(
                        f"{message} Database appears to be fully upgraded but unstamped. Stamping with latest version...",
                        fg="yellow",
                    )
                    # Stamp with the latest migration since create_all() already created it
                    if is_managed:
                        from alembic.script import ScriptDirectory

                        script = ScriptDirectory.from_config(alembic_cfg)
                        head_rev = script.get_current_head()
                        if head_rev:
                            from sqlalchemy import text

                            connection.execute(text("DELETE FROM alembic_version"))
                            connection.execute(
                                text(
                                    f"INSERT INTO alembic_version (version_num) VALUES ('{head_rev}')"
                                )
                            )
                    else:
                        command.stamp(alembic_cfg, "head")
                    click.secho("Database stamped with latest.", fg="green")
                else:
                    # Brand new empty DB that somehow reached here without _ensure_tables_created catching it
                    click.secho(
                        "Empty database detected. Running migrations from scratch...",
                        fg="yellow",
                    )

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
        error_msg = str(e)
        if not error_msg:
            error_msg = repr(e)
        click.secho(
            f"An error occurred during the database upgrade: {error_msg}", fg="red"
        )
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


@database.command(name="backup")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="The output path for the JSON backup file. If not provided, it will be saved in the configured backups directory.",
)
@click.pass_context
def backup_db(ctx: click.Context, output: str | None):
    """Backups all database records to a JSON file."""
    app_context: AppContext = ctx.obj["app_context"]
    source_db = app_context.db

    if not output:
        backup_dir = app_context.settings.get("paths.backups")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"{backup_dir}/db_data_backup_{timestamp}.json"

    MODELS_TO_BACKUP = [
        models.User,
        models.Server,
        models.ServerBan,
        models.Setting,
        models.Plugin,
        models.RegistrationToken,
        models.Player,
        models.AuditLog,
    ]

    # Include alembic version metadata
    backup_data = {}

    alembic_ini_path = files("bedrock_server_manager").joinpath("db/alembic.ini")
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("skip_logging_config", "true")

    def default_serializer(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    try:
        # Get the current alembic revision
        engine = app_context.db.engine
        if engine:
            with engine.connect() as connection:
                inspector = inspect(connection)
                if inspector.has_table("alembic_version"):
                    from sqlalchemy import text

                    current_rev = connection.execute(
                        text("SELECT version_num FROM alembic_version")
                    ).scalar_one_or_none()
                    if current_rev:
                        backup_data["_metadata"] = {"alembic_version": current_rev}

        with source_db.session_manager() as session:  # type: ignore
            for model in MODELS_TO_BACKUP:
                model_name = model.__name__
                click.echo(f"Backing up table: {model_name}...")

                records = session.query(model).all()
                model_data = []
                for record in records:
                    record_dict = {
                        c.name: getattr(record, c.name)
                        for c in record.__table__.columns
                    }
                    model_data.append(record_dict)

                backup_data[model_name] = model_data
                click.echo(f"  Backed up {len(model_data)} records for {model_name}.")

        with open(output, "w") as f:
            json.dump(backup_data, f, default=default_serializer, indent=4)

        click.secho(f"\nDatabase data backup successful! Saved to {output}", fg="green")

    except Exception as e:
        click.secho(
            f"\nAn error occurred during data backup: {e}", fg="red", exc_info=True
        )
        raise click.Abort()


@database.command(name="restore")
@click.option(
    "--input",
    "-i",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
    help="The input path for the JSON backup file.",
)
@click.pass_context
def restore_db(ctx: click.Context, input: str):
    """Restores database records from a JSON file. Wipes existing data!"""
    app_context: AppContext = ctx.obj["app_context"]
    target_db = app_context.db

    click.secho("Database Restore Utility", fg="cyan", bold=True)
    click.echo(f"This utility will restore data from: {input}")
    click.secho(
        "WARNING: This operation will WIPE ALL EXISTING DATA in the current database before restoring.",
        fg="red",
        bold=True,
    )

    if not questionary.confirm(
        "Are you absolutely sure you want to proceed? ALL CURRENT DATA WILL BE LOST.",
        default=False,
    ).ask():
        click.secho("Operation cancelled.", fg="yellow")
        raise click.Abort()

    # The order matters for restoring to satisfy foreign keys
    # To delete, we go in reverse order.
    MODELS_TO_RESTORE = [
        models.User,
        models.Server,
        models.ServerBan,
        models.Setting,
        models.Plugin,
        models.RegistrationToken,
        models.Player,
        models.AuditLog,
    ]

    try:
        with open(input, "r") as f:
            backup_data = json.load(f)
    except Exception as e:
        click.secho(f"Failed to read backup file: {e}", fg="red")
        raise click.Abort()

    # Check for version mismatch
    engine = app_context.db.engine
    current_db_rev = None
    if engine:
        with engine.connect() as connection:
            inspector = inspect(connection)
            if inspector.has_table("alembic_version"):
                from sqlalchemy import text

                current_db_rev = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one_or_none()

    backup_rev = backup_data.get("_metadata", {}).get("alembic_version")
    if current_db_rev and backup_rev and current_db_rev != backup_rev:
        click.secho(f"\nWARNING: Database version mismatch!", fg="yellow", bold=True)
        click.secho(f"Current database version: {current_db_rev}", fg="yellow")
        click.secho(f"Backup file database version: {backup_rev}", fg="yellow")
        click.secho(
            "Restoring data to a different schema version may cause errors or data corruption.",
            fg="red",
        )
        if not questionary.confirm(
            "Do you still want to proceed despite the version mismatch?", default=False
        ).ask():
            click.secho("Operation cancelled.", fg="yellow")
            raise click.Abort()
    elif not backup_rev:
        click.secho(
            "\nWARNING: The backup file does not contain database version metadata.",
            fg="yellow",
        )
        if not questionary.confirm(
            "Do you want to proceed without version verification?", default=True
        ).ask():
            click.secho("Operation cancelled.", fg="yellow")
            raise click.Abort()

    try:
        with target_db.session_manager() as session:  # type: ignore
            # 1. Delete existing data (reverse order)
            click.echo("Wiping existing data...")
            for model in reversed(MODELS_TO_RESTORE):
                model_name = model.__name__
                count = session.query(model).delete()
                click.echo(f"  Deleted {count} records from {model_name}.")

            # 2. Insert new data
            click.echo("\nRestoring data...")
            for model in MODELS_TO_RESTORE:
                model_name = model.__name__
                if model_name not in backup_data:
                    click.secho(
                        f"  Warning: No backup data found for {model_name}.",
                        fg="yellow",
                    )
                    continue

                records_data = backup_data[model_name]
                new_objects = []
                for record_dict in records_data:
                    # Convert ISO datetime strings back to datetime objects
                    for col in getattr(model, "__table__").columns:
                        col_name = col.name
                        if (
                            col_name in record_dict
                            and record_dict[col_name] is not None
                        ):
                            # Heuristic: if it looks like an ISO format string and the column is DateTime
                            is_datetime = type(col.type).__name__ == "DateTime"
                            if not is_datetime and target_db.engine:
                                try:
                                    is_datetime = isinstance(
                                        col.type,
                                        target_db.engine.dialect.type_compiler.process(
                                            col.type
                                        ).__class__,
                                    )
                                except Exception:
                                    pass

                            if is_datetime:
                                if isinstance(record_dict[col_name], str):
                                    try:
                                        # Handle standard isoformat
                                        record_dict[col_name] = datetime.fromisoformat(
                                            record_dict[col_name]
                                        )
                                    except ValueError:
                                        pass

                    new_objects.append(model(**record_dict))

                session.bulk_save_objects(new_objects)
                click.echo(f"  Restored {len(new_objects)} records for {model_name}.")

            session.commit()
            click.secho("\nDatabase data restore successful!", fg="green")

    except Exception as e:
        click.secho(f"\nAn error occurred during data restore: {e}", fg="red")
        click.secho(
            "The database might be in an inconsistent state. Please restore from a secure backup.",
            fg="yellow",
        )
        raise click.Abort()
