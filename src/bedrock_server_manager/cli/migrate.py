import click
from alembic.config import Config
from alembic import command
from importlib.resources import files


@click.command()
def migrate():
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
