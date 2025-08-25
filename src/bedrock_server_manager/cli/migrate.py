import click

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
    """Migration tools."""
    pass


@migrate.command("old-config")
@click.pass_context
def migrate_old_config(ctx: click.Context):
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
