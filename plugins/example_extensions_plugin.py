"""
Example Extensions Plugin for Bedrock Server Manager
Demonstrates how to add custom CLI commands and FastAPI routers.
"""

from bedrock_server_manager import PluginBase
import click
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

# Attempt to import get_current_user for securing FastAPI endpoints
# This might fail if the main app structure changes, so handle import error gracefully for the example.
try:
    from bedrock_server_manager.web.auth_utils import get_current_user

    HAS_AUTH_DEPENDENCY = True
except ImportError:
    HAS_AUTH_DEPENDENCY = False

    # Define a dummy dependency if the real one can't be imported (e.g., in a minimal test env)
    async def get_current_user():  # Dummy dependency
        return {"username": "anonymous_test_user"}


# Define a version for this plugin
VERSION = "1.0.0"


# --- CLI Command Example ---
@click.group("explug")
def example_plugin_cli_group():
    """A top-level command group from the Example Extensions Plugin."""
    pass


@example_plugin_cli_group.command("hello")
@click.option("--name", default="World", help="The person to greet from CLI.")
@click.pass_context  # Example of accessing plugin logger via context if needed, though not used here
def hello_cli_command(ctx, name):
    """Greets someone from the plugin's CLI."""
    # Accessing logger if plugin instance was passed in ctx, e.g. ctx.obj['plugin_manager'].plugins[name].logger
    # For simplicity, this example doesn't pass the plugin instance itself to the command.
    # The plugin's own logger (self.logger in PluginBase) is for plugin's internal logging.
    click.echo(
        f"Hello, {name}, from the Example Extensions Plugin's CLI command! (Plugin v{VERSION})"
    )


@example_plugin_cli_group.command("info")
def info_cli_command():
    """Shows info about this example plugin CLI extension."""
    click.echo(
        "This is the 'info' command of the 'explug' group from ExampleExtensionsPlugin."
    )
    click.echo(f"Plugin Version: {VERSION}")
    if not HAS_AUTH_DEPENDENCY:
        click.echo(
            "Note: FastAPI auth dependency 'get_current_user' was not found during plugin load."
        )


# --- FastAPI Router Example ---
# Create a list of dependencies for the router
router_dependencies = [Depends(get_current_user)] if HAS_AUTH_DEPENDENCY else []

example_plugin_api_router = APIRouter(
    prefix="/example_plugin_api",  # URL prefix for all routes in this router
    tags=["Example Plugin API"],  # Tag for OpenAPI documentation
    dependencies=router_dependencies,  # Apply dependencies to all routes in this router
)


@example_plugin_api_router.get("/status")
async def get_plugin_api_status():
    """Returns the status of this example plugin's API."""
    return {
        "plugin_name": "Example Extensions Plugin",
        "version": VERSION,
        "api_status": "operational",
    }


@example_plugin_api_router.get("/greet/{name}")
async def greet_name_via_api(name: str):
    """Greets a person by name via a plugin's FastAPI endpoint."""
    return {
        "message": f"Hello, {name}, from the Example Extensions Plugin's API! (Plugin v{VERSION})"
    }


@example_plugin_api_router.get(
    "/custom-page", response_class=HTMLResponse, tags=["plugin-ui"]
)
async def get_custom_html_page():
    """Serves a simple custom HTML page from the plugin."""
    html_content = f"""
    <html>
        <head>
            <title>Plugin Page</title>
        </head>
        <body>
            <h1>Welcome to a Custom Page from Example Extensions Plugin v{VERSION}!</h1>
            <p>This page is served directly by a plugin's FastAPI router.</p>
            <p><a href="/example_plugin_api/status">Check API Status</a></p>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)


class ExampleExtensionsPlugin(PluginBase):
    version = VERSION  # Required class attribute

    def on_load(self):
        self.logger.info(
            f"Example Extensions Plugin v{self.version} loaded successfully."
        )
        if not HAS_AUTH_DEPENDENCY:
            self.logger.warning(
                "FastAPI auth dependency 'get_current_active_user' not found. API endpoints might be unsecured if this is unintentional."
            )
        self.logger.info(
            "This plugin demonstrates adding a CLI command group 'explug' with subcommands, and a FastAPI router at '/example_plugin_api'."
        )

    def get_cli_commands(self):
        self.logger.info(
            f"ExampleExtensionsPlugin v{self.version}: Providing CLI command group 'explug'."
        )
        # Return the top-level group. Click will handle its subcommands.
        return [example_plugin_cli_group]

    def get_fastapi_routers(self):
        self.logger.info(
            f"ExampleExtensionsPlugin v{self.version}: Providing FastAPI router for '/example_plugin_api'."
        )
        return [example_plugin_api_router]

    def on_unload(self):
        self.logger.info(f"Example Extensions Plugin v{self.version} unloaded.")
