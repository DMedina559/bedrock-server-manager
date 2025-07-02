# bedrock_server_manager/cli/plugins.py
"""
Defines the `bsm plugin` command group for interacting with the plugin system.

This module provides CLI tools for managing plugins within the Bedrock Server Manager.
Functionality includes:

    -   Listing all discoverable plugins and their current enabled/disabled status and version.
    -   Enabling or disabling specific plugins.
    -   Triggering a reload of all plugins by the plugin manager.
    -   Manually triggering custom plugin events with optional JSON payloads for testing
        or administrative purposes.

Commands primarily interact with the API functions in
:mod:`~bedrock_server_manager.api.plugins`. An interactive workflow is
provided if the main `plugin` command is called without subcommands.
"""
import logging
from typing import Dict, Optional, Any

import click
import questionary
from click.core import Context

# Make sure this import points to your API functions module
from bedrock_server_manager.api import plugins as plugins_api
from bedrock_server_manager.config.const import app_name_title
from bedrock_server_manager.cli.utils import handle_api_response as _handle_api_response
from bedrock_server_manager.error import BSMError, UserInputError

logger = logging.getLogger(__name__)


def _print_plugin_table(plugins: Dict[str, Dict[str, Any]]):
    """
    Internal helper to print a formatted table of plugins, their statuses, and versions.

    Args:
        plugins (Dict[str, Dict[str, Any]]): A dictionary where keys are plugin
            names and values are dictionaries containing plugin metadata,
            including "enabled" (bool) and "version" (str).
    """
    if not plugins:
        click.secho("No plugins found or configured.", fg="yellow")
        return

    click.secho(
        f"{app_name_title} - Plugin Statuses & Versions", fg="magenta", bold=True
    )

    plugin_names = list(plugins.keys())
    versions = [config.get("version", "N/A") for config in plugins.values()]

    max_name_len = max(len(name) for name in plugin_names) if plugin_names else 20
    max_version_len = max(
        (max(len(v) for v in versions) if versions else 0), len("Version")
    )
    max_status_len = len("Disabled")

    header = f"{'Plugin Name':<{max_name_len}} | {'Status':<{max_status_len}} | {'Version':<{max_version_len}}"
    click.secho(header, underline=True)
    click.secho("-" * len(header))

    for name, config in sorted(plugins.items()):
        is_enabled = config.get("enabled", False)
        version = config.get("version", "N/A")

        status_str = "Enabled" if is_enabled else "Disabled"
        status_color = "green" if is_enabled else "red"

        click.echo(f"{name:<{max_name_len}} | ", nl=False)
        click.secho(f"{status_str:<{max_status_len}}", fg=status_color, nl=False)
        click.echo(f" | {version:<{max_version_len}}")


def interactive_plugin_workflow():
    """
    Guides the user through an interactive session to enable or disable plugins.

    This workflow:

        1. Fetches all discoverable plugins and their current statuses using
           :func:`~bedrock_server_manager.api.plugins.get_plugin_statuses`.
        2. Displays them in a table using :func:`~._print_plugin_table`.
        3. Presents a `questionary.checkbox` prompt allowing the user to toggle the
           enabled state of multiple plugins.
        4. Calculates which plugins need to be enabled or disabled based on changes.
        5. Calls :func:`~bedrock_server_manager.api.plugins.set_plugin_status` for each
           plugin whose state was changed.
        6. If any changes were successfully applied, triggers a plugin reload via
           :func:`~bedrock_server_manager.api.plugins.reload_plugins`.
        7. Finally, displays the updated plugin status table.

    Handles user cancellation (Ctrl+C) and API errors gracefully.
    """
    try:
        response = plugins_api.get_plugin_statuses()
        if response.get("status") != "success":
            # Use _handle_api_response for consistent error message and abort
            _handle_api_response(
                response, "Failed to retrieve plugin statuses"
            )  # Removed error_message_prefix as _handle_api_response prepends "Error: "
            return

        plugins: Dict[str, Dict[str, Any]] = response.get("plugins", {})
        if not plugins:
            click.secho("No plugins found or configured to edit.", fg="yellow")
            return

        _print_plugin_table(plugins)
        click.echo()  # Add a newline for better spacing before prompt

        initial_enabled_plugins = {
            name
            for name, config_dict in plugins.items()
            if config_dict.get("enabled", False)
        }

        choices = []
        for name, config_dict in sorted(plugins.items()):  # Sort for consistent order
            is_enabled = config_dict.get("enabled", False)
            version = config_dict.get("version", "N/A")
            choice_title = f"{name} (v{version})"
            choices.append(
                questionary.Choice(title=choice_title, value=name, checked=is_enabled)
            )

        selected_plugin_names_list = questionary.checkbox(
            "Toggle plugins (space to select/deselect, enter to confirm):",  # Clarified prompt
            choices=choices,
        ).ask()

        if selected_plugin_names_list is None:  # User cancelled (e.g., Esc)
            click.secho("\nOperation cancelled by user.", fg="yellow")
            return

        final_enabled_plugins = set(selected_plugin_names_list)
        plugins_to_enable = sorted(
            list(final_enabled_plugins - initial_enabled_plugins)
        )  # Sort for consistent processing order
        plugins_to_disable = sorted(
            list(initial_enabled_plugins - final_enabled_plugins)
        )  # Sort

        if not plugins_to_enable and not plugins_to_disable:
            click.secho("\nNo changes made to plugin statuses.", fg="cyan")
            # _print_plugin_table(plugins) # Optionally re-print if no changes
            return

        click.echo("\nApplying changes...")
        changes_made_successfully = False
        for name in plugins_to_enable:
            click.echo(f"Enabling plugin '{name}'... ", nl=False)
            api_response = plugins_api.set_plugin_status(name, True)
            if api_response.get("status") == "success":
                click.secho("OK", fg="green")
                changes_made_successfully = True
            else:
                error_msg = api_response.get("message", "Failed to enable.")
                click.secho(f"Failed: {error_msg}", fg="red")

        for name in plugins_to_disable:
            click.echo(f"Disabling plugin '{name}'... ", nl=False)
            api_response = plugins_api.set_plugin_status(name, False)
            if api_response.get("status") == "success":
                click.secho("OK", fg="green")
                changes_made_successfully = True
            else:
                error_msg = api_response.get("message", "Failed to disable.")
                click.secho(f"Failed: {error_msg}", fg="red")

        if changes_made_successfully:
            click.secho("\nPlugin configuration updated.", fg="green")
            try:
                click.secho("Reloading plugins...", fg="cyan")
                reload_response = plugins_api.reload_plugins()
                if reload_response.get("status") == "success":
                    click.secho(
                        reload_response.get(
                            "message", "Plugins reloaded successfully."
                        ),
                        fg="green",
                    )
                else:
                    _handle_api_response(reload_response, "Failed to reload plugins")
            except BSMError as e_reload:
                click.secho(f"\nError reloading plugins: {e_reload}", fg="red")
        else:
            click.secho(
                "\nNo changes were successfully applied to plugin statuses.",
                fg="yellow",
            )

        # Display final statuses
        click.echo("\nFetching updated plugin statuses...")
        final_response = plugins_api.get_plugin_statuses()
        if final_response.get("status") == "success":
            _print_plugin_table(final_response.get("plugins", {}))
        else:
            click.secho(
                "Could not retrieve final plugin statuses after update.", fg="red"
            )

    except (BSMError, KeyboardInterrupt, click.Abort) as e:
        if isinstance(
            e, (KeyboardInterrupt, click.Abort)
        ):  # Explicitly check for Abort too
            click.secho("\nOperation cancelled by user.", fg="yellow")
        else:  # BSMError
            click.secho(
                f"\nAn error occurred during plugin configuration: {e}", fg="red"
            )


@click.group(invoke_without_command=True)
@click.pass_context
def plugin(ctx: Context):
    """
    Manages plugins for the Bedrock Server Manager.

    This command group provides subcommands to list, enable, disable, and
    reload plugins. If invoked without any subcommand, it defaults to
    launching an interactive workflow (:func:`~.interactive_plugin_workflow`)
    for managing plugin statuses.
    """
    if ctx.invoked_subcommand is None:
        interactive_plugin_workflow()


@plugin.command("list")
def list_plugins():
    """
    Lists all discoverable plugins, their versions, and current enabled/disabled status.

    Retrieves plugin information via the API and displays it in a formatted table.

    Calls API: :func:`~bedrock_server_manager.api.plugins.get_plugin_statuses`.
    """
    try:
        response = plugins_api.get_plugin_statuses()
        if response.get("status") == "success":
            plugins = response.get("plugins", {})
            _print_plugin_table(plugins)  # Internal helper for table formatting
        else:
            # Let _handle_api_response manage error display and abort
            _handle_api_response(response, "Failed to retrieve plugin statuses")
    except BSMError as e:
        click.secho(f"Error listing plugins: {e}", fg="red")
        # Consider click.Abort() here if BSMError should halt execution.


@plugin.command("enable")
@click.argument("plugin_name", required=False)
def enable_plugin(plugin_name: Optional[str]):
    """
    Enables a specific plugin.

    If `PLUGIN_NAME` is provided, this command attempts to enable that specific
    plugin. If `PLUGIN_NAME` is omitted, it falls back to the
    :func:`~.interactive_plugin_workflow` for guided plugin management.

    After enabling, it's recommended to run `bsm plugin reload` for changes
    to take full effect if not handled automatically by the API.

    Calls API: :func:`~bedrock_server_manager.api.plugins.set_plugin_status`.
    """
    if not plugin_name:
        interactive_plugin_workflow()
        return

    click.echo(f"Attempting to enable plugin '{plugin_name}'...")
    try:
        response = plugins_api.set_plugin_status(plugin_name, True)
        # _handle_api_response will show success/error from API.
        # Default success message if API doesn't provide one.
        _handle_api_response(response, f"Plugin '{plugin_name}' status set to enabled.")
    except UserInputError as e:  # Typically for "plugin not found" from API
        click.secho(f"Error: {e}", fg="red")
        raise click.Abort()
    except BSMError as e:  # Other BSM errors
        click.secho(f"Failed to enable plugin '{plugin_name}': {e}", fg="red")
        raise click.Abort()


@plugin.command("disable")
@click.argument("plugin_name", required=False)
def disable_plugin(plugin_name: Optional[str]):
    """
    Disables a specific plugin.

    If `PLUGIN_NAME` is provided, this command attempts to disable that
    specific plugin. If `PLUGIN_NAME` is omitted, it falls back to the
    :func:`~.interactive_plugin_workflow` for guided plugin management.

    After disabling, it's recommended to run `bsm plugin reload` for changes
    to take full effect if not handled automatically by the API.

    Calls API: :func:`~bedrock_server_manager.api.plugins.set_plugin_status`.
    """
    if not plugin_name:
        interactive_plugin_workflow()
        return

    click.echo(f"Attempting to disable plugin '{plugin_name}'...")
    try:
        response = plugins_api.set_plugin_status(plugin_name, False)
        _handle_api_response(
            response, f"Plugin '{plugin_name}' status set to disabled."
        )
    except UserInputError as e:  # Typically for "plugin not found" from API
        click.secho(f"Error: {e}", fg="red")
        raise click.Abort()
    except BSMError as e:  # Other BSM errors
        click.secho(f"Failed to disable plugin '{plugin_name}': {e}", fg="red")
        raise click.Abort()


@plugin.command("reload")
def reload_plugins_cli():
    """
    Triggers the plugin manager to reload all plugins.

    This command instructs the application's plugin manager to re-scan for
    plugins and reload them. This is useful after enabling/disabling plugins
    or when plugin code has been updated.

    Calls API: :func:`~bedrock_server_manager.api.plugins.reload_plugins`.
    """
    click.echo("Attempting to reload plugins...")
    try:
        response = plugins_api.reload_plugins()
        # _handle_api_response will show success or error message from API
        _handle_api_response(response, "Plugins reloaded successfully.")
    except BSMError as e:
        click.secho(f"Error reloading plugins: {e}", fg="red")
        raise click.Abort()  # Abort on BSMError for consistency
    except Exception as e:
        click.secho(
            f"An unexpected error occurred during plugin reload: {e}",
            fg="red",
            err=True,
        )
        logger.error(
            f"Unexpected error in 'plugin reload' CLI command: {e}", exc_info=True
        )
        raise click.Abort()


@plugin.command("trigger-event")
@click.argument("event_name", required=True)
@click.option(
    "--payload-json",
    metavar="<JSON_STRING>",
    help="Optional JSON string to use as the event payload.",
)
def trigger_event_cli(event_name: str, payload_json: Optional[str]):
    """
    Triggers a custom plugin event with an optional JSON payload.

    This command allows developers or administrators to manually trigger a
    named event within the plugin system. An optional JSON string can be
    provided as a payload, which will be parsed into a dictionary and
    passed to the event handlers.

    Calls API: :func:`~bedrock_server_manager.api.plugins.trigger_external_plugin_event_api`.
    """
    import json  # Local import for json

    click.echo(f"Attempting to trigger custom plugin event '{event_name}'...")

    payload_dict: Optional[Dict[str, Any]] = None
    if payload_json:
        try:
            payload_dict = json.loads(payload_json)
            if not isinstance(payload_dict, dict):
                click.secho(
                    "Error: --payload-json must be a valid JSON object (dictionary).",
                    fg="red",
                )
                return
            click.echo(f"With payload: {payload_dict}")
        except json.JSONDecodeError as e:
            click.secho(f"Error: Invalid JSON provided for payload: {e}", fg="red")
            return
        except Exception as e:  # Catch any other unexpected error during parsing
            click.secho(f"Error parsing payload: {e}", fg="red")
            return

    try:
        response = plugins_api.trigger_external_plugin_event_api(
            event_name, payload_dict
        )

        if response.get("status") == "success":
            success_msg = response.get(
                "message", f"Event '{event_name}' triggered successfully."
            )
            click.secho(success_msg, fg="green")
        else:
            _handle_api_response(
                response, error_message_prefix=f"Failed to trigger event '{event_name}'"
            )
    except (
        UserInputError
    ) as e:  # Catch UserInputError from the API function if event_name is missing
        click.secho(f"Error: {e}", fg="red")
    except BSMError as e:  # Catch other BSM errors
        click.secho(f"Error triggering event '{event_name}': {e}", fg="red")
    except Exception as e:
        click.secho(f"An unexpected error occurred: {e}", fg="red", err=True)
        logger.error(
            f"Unexpected error in 'plugin event trigger' CLI command: {e}",
            exc_info=True,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    plugin()
