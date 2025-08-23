# <PLUGIN_DIR>/plugins/event_sender_plugin/__init__.py
"""
Plugin to provide a web UI for sending custom plugin events.
"""
from pathlib import Path
from typing import Dict, Any

from fastapi import APIRouter, Request, Depends
import click  # For prompts and colored output
import json  # For parsing JSON payload

from bedrock_server_manager.web import get_admin_user
from bedrock_server_manager import PluginBase


class EventSenderPlugin(PluginBase):
    version = "1.1.1"

    def on_load(self):
        self.logger.info(
            f"Plugin '{self.name}' v{self.version} loaded. Event sender page available at /event_sender/page"
        )

        self.router = APIRouter(
            tags=["Event Sender Plugin"]  # Tag for OpenAPI documentation
        )
        self._define_routes()
        self.logger.info(f"EventSenderPlugin v{self.version} initialized.")

    def _define_routes(self):
        @self.router.get(
            "/event-sender/page",
            name="Event Sender Page",  # For url_for
            summary="Custom Event Sender",  # For dynamic submenu in UI
            tags=["plugin-ui"],  # For discovery by dynamic submenu
        )
        async def get_event_sender_page(
            request: Request,
            current_user: Dict[str, Any] = Depends(get_admin_user),
        ):
            self.logger.debug(f"Serving event sender page for plugin: {self.name}")
            templates_env = self.api.app_context.templates
            # Template name will be relative to one of the template folders.
            # If this plugin's "templates" folder is registered, Jinja2 will find it.
            return templates_env.TemplateResponse(
                "event_sender_page.html", {"request": request}
            )

    def on_unload(self):
        self.logger.info(f"Plugin '{self.name}' v{self.version} unloaded.")

    def get_fastapi_routers(self):
        self.logger.debug(f"Providing FastAPI router for {self.name}")
        return [self.router]

    def get_template_paths(self) -> list[Path]:
        """Returns the path to this plugin's templates directory."""
        plugin_root_dir = Path(__file__).parent
        template_dir = plugin_root_dir / "templates"
        # It's good practice to ensure the directory actually exists before returning it
        if not template_dir.is_dir():
            self.logger.warning(
                f"Template directory not found for {self.name} at {template_dir}. Page might not load."
            )
            return []
        return [template_dir]

    # --- CLI Menu Item for Sending Custom Events ---
    def _cli_menu_send_custom_event_interactive(self, ctx: "click.Context"):
        """Handler for the interactive custom event sender CLI menu item."""

        self.logger.info(f"'{self.name}' CLI: Interactive event sender started.")
        click.secho("--- Send Custom Plugin Event ---", fg="magenta")

        event_name = click.prompt("Enter Event Name (e.g., namespace:event_name)")
        if (
            not event_name
            or ":" not in event_name
            or event_name.startswith(":")
            or event_name.endswith(":")
        ):
            click.secho(
                "Invalid event name format. Must be 'namespace:event_name'. Aborting.",
                fg="red",
            )
            return

        payload_str = click.prompt(
            "Enter Event Payload (JSON, or leave empty for no payload)",
            default="",
            show_default=False,
        )

        event_payload = {}
        if payload_str.strip():  # If payload string is not empty
            try:
                event_payload = json.loads(payload_str)
                if not isinstance(event_payload, dict):
                    click.secho(
                        "Invalid payload: JSON string must represent an object (dictionary). Aborting.",
                        fg="red",
                    )
                    return
            except json.JSONDecodeError as e:
                click.secho(f"Invalid JSON in payload: {e}. Aborting.", fg="red")
                return

        click.secho(f"\nPreparing to send event:", fg="yellow")
        click.secho(f"  Name:    {event_name}", fg="yellow")
        click.secho(
            f"  Payload: {json.dumps(event_payload, indent=2)}", fg="yellow"
        )  # Pretty print payload for confirmation

        if not click.confirm("Proceed to send this event?", default=False):
            click.secho("Event sending cancelled by user.", fg="yellow")
            return

        if self.api:
            try:
                self.api.send_event(event_name, **event_payload)
                click.secho(f"Event '{event_name}' successfully sent.", fg="green")
            except Exception as e:
                self.logger.error(
                    f"API error sending event '{event_name}': {e}", exc_info=True
                )
                click.secho(f"Error sending event '{event_name}': {e}", fg="red")
        else:
            click.secho("Error: Plugin API not available. Cannot send event.", fg="red")

    def get_cli_menu_items(self) -> list[dict[str, any]]:
        self.logger.debug(f"Providing CLI menu items for {self.name}")
        return [
            {
                "name": "Send Custom Event",
                "handler": self._cli_menu_send_custom_event_interactive,
            }
        ]
