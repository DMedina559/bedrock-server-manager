from math import e
import click
import questionary

from ..config import bcm_config
from ..config.const import app_name_title
from .service import interactive_web_service_workflow


@click.command("setup", help="Run an interactive setup to configure the manager.")
@click.pass_context
def setup(ctx: click.Context):
    """
    An interactive command to guide the user through setting up the
    Bedrock Server Manager. It configures the data directory, web UI settings,
    and database connection.
    """
    try:
        from ..context import AppContext

        app_context: AppContext = ctx.obj["app_context"]
        click.secho(f"{app_name_title} - Setup", fg="cyan")

        current_config = bcm_config.load_config()

        # --- Prompt for Data Directory ---
        default_data_dir = bcm_config._config_dir
        data_dir = questionary.text(
            "Enter the path for the data directory:",
            default=current_config.get("data_dir", default_data_dir),
        ).ask()
        if data_dir:
            bcm_config.set_config_value("data_dir", data_dir)
            click.secho(f"Data directory set to: {data_dir}", fg="green")

        # --- Prompt for Database URL ---
        click.echo("\n--- Database Configuration ---")
        if questionary.confirm(
            "Do you want to configure an advanced database connection (e.g., PostgreSQL)?",
            default=False,
        ).ask():
            db_url = questionary.text(
                "Enter the full database URL (e.g., postgresql://user:pass@host/dbname):",
                default=current_config.get("db_url", ""),
            ).ask()
            if db_url:
                bcm_config.set_config_value("db_url", db_url)
                click.secho(f"Database URL set to: {db_url}", fg="green")
        else:
            # If they say no, ensure the db_url is cleared so the default is used
            if "db_url" in current_config:
                config = bcm_config.load_config()
                del config["db_url"]
                bcm_config.save_config(config)
            click.echo("Using the default SQLite database.")

        # --- Load AppContext ---
        app_context.load()
        settings = app_context.settings

        # --- Prompt for Web Host and Port ---
        click.echo("\n--- Web UI Configuration ---")
        web_host = questionary.text(
            "Enter the web UI host address:",
            default=settings.get("web.host", "127.0.0.1"),
        ).ask()
        if web_host:
            settings.set("web.host", web_host)

        web_port = questionary.text(
            "Enter the web UI port:",
            default=str(settings.get("web.port", "11325")),
            validate=lambda text: text.isdigit(),
        ).ask()
        if web_port:
            settings.set("web.port", int(web_port))

        click.secho(
            f"Web UI will be hosted at: http://{web_host}:{web_port}", fg="green"
        )

        # --- Prompt for Service Config ---
        click.echo("\n--- Service Configuration ---")
        if questionary.confirm(
            f"Do you want to configure a system service for {app_name_title}?",
            default=False,
        ).ask():
            interactive_web_service_workflow(app_context)
        else:
            click.echo(
                "Skipping service configuration. You can set it up later using the 'service' command."
            )

        click.secho(
            "\nSetup complete! Your settings have been saved.", fg="cyan", bold=True
        )
    except Exception as e:
        click.secho(f"Error during configuration: {e}", fg="red")
    except (click.Abort, KeyboardInterrupt):
        click.secho("\nOperation cancelled.", fg="yellow")
