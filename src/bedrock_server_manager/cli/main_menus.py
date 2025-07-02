# bedrock_server_manager/cli/main_menus.py
"""Defines the main interactive menu flows for the application.

This module uses `questionary` to create a user-friendly, menu-driven
interface that acts as a front-end to the application's underlying `click`
commands. It provides a guided experience for users who prefer not to use
direct command-line flags. The menus are built dynamically based on the
host system's capabilities.
"""

import logging

import click
import questionary
from questionary import Separator

from bedrock_server_manager.config.const import app_name_title
from bedrock_server_manager.core.manager import BedrockServerManager
from bedrock_server_manager.error import UserExitError
from bedrock_server_manager.utils.get_utils import _get_splash_text

from .utils import get_server_name_interactively, list_servers

logger = logging.getLogger(__name__)


def _world_management_menu(ctx: click.Context, server_name: str):
    """Displays a sub-menu for world management actions.

    Args:
        ctx: The current click command context.
        server_name: The name of the server being managed.
    """
    # This sub-menu is static as it doesn't depend on OS capabilities.
    world_group = ctx.obj["cli"].get_command(ctx, "world")
    if not world_group:
        click.secho("Error: World command group not found.", fg="red")
        return

    menu_map = {
        "Install/Replace World": world_group.get_command(ctx, "install"),
        "Export Current World": world_group.get_command(ctx, "export"),
        "Reset Current World": world_group.get_command(ctx, "reset"),
        "Back": None,
    }

    while True:
        choice = questionary.select(
            f"World Management for '{server_name}':",
            choices=list(menu_map.keys()),
            use_indicator=True,
        ).ask()

        if choice is None or choice == "Back":
            return
        command = menu_map.get(choice)
        if command:
            ctx.invoke(command, server_name=server_name)
            break


def _backup_restore_menu(ctx: click.Context, server_name: str):
    """Displays a sub-menu for backup and restore actions.

    Args:
        ctx: The current click command context.
        server_name: The name of the server being managed.
    """
    # This sub-menu is also static.
    backup_group = ctx.obj["cli"].get_command(ctx, "backup")
    if not backup_group:
        click.secho("Error: Backup command group not found.", fg="red")
        return

    menu_map = {
        "Create Backup": backup_group.get_command(ctx, "create"),
        "Restore from Backup": backup_group.get_command(ctx, "restore"),
        "Prune Old Backups": backup_group.get_command(ctx, "prune"),
        "Back": None,
    }

    while True:
        choice = questionary.select(
            f"Backup/Restore for '{server_name}':",
            choices=list(menu_map.keys()),
            use_indicator=True,
        ).ask()

        if choice is None or choice == "Back":
            return
        command = menu_map.get(choice)
        if command:
            ctx.invoke(command, server_name=server_name)
            break


def main_menu(ctx: click.Context):
    """Displays the main application menu and drives interactive mode.

    Args:
        ctx: The root click command context.

    Raises:
        UserExitError: Propagated to signal a clean exit from the application.
    """
    bsm: BedrockServerManager = ctx.obj["bsm"]
    cli = ctx.obj["cli"]

    while True:
        try:
            click.clear()
            click.secho(f"{app_name_title} - Main Menu", fg="magenta", bold=True)
            click.secho(_get_splash_text(), fg="yellow")

            # Display server list for context before showing the menu
            ctx.invoke(list_servers, loop=False, server_name=None)

            # --- Dynamically build menu choices ---
            # Fetch server data once to build the menu and reuse the list
            servers_data, _ = bsm.get_servers_data()
            server_names = [s["name"] for s in servers_data]

            menu_choices = ["Install New Server"]

            if server_names:
                menu_choices.append("Manage Existing Server")

            menu_choices.extend(["Manage Plugins", "Exit"])

            choice = questionary.select(
                "\nChoose an action:",
                choices=menu_choices,
                use_indicator=True,
            ).ask()

            if choice is None or choice == "Exit":
                raise UserExitError()

            if choice == "Install New Server":
                server_group = cli.get_command(ctx, "server")
                install_cmd = server_group.get_command(ctx, "install")
                ctx.invoke(install_cmd)
                questionary.press_any_key_to_continue(
                    "Press any key to return to the main menu..."
                ).ask()

            elif choice == "Manage Existing Server":
                # This option is only shown if servers exist.
                # Pass the already-fetched list of names to the selection utility.
                server_name = get_server_name_interactively()
                if server_name:
                    manage_server_menu(ctx, server_name)

            elif choice == "Manage Plugins":
                # Invoke the interactive plugin editor
                plugin_group = cli.get_command(ctx, "plugin")
                edit_cmd = plugin_group.get_command(ctx, "enable")
                ctx.invoke(edit_cmd)
                questionary.press_any_key_to_continue(
                    "Press any key to return to the main menu..."
                ).ask()

        except UserExitError:
            click.secho("\nExiting application. Goodbye!", fg="green")
            raise
        except (click.Abort, KeyboardInterrupt):
            click.echo("\nAction cancelled. Returning to the main menu.")
            click.pause()
        except Exception as e:
            logger.error(f"Main menu loop error: {e}", exc_info=True)
            click.secho(f"\nAn unexpected error occurred: {e}", fg="red")
            click.pause("Press any key to return to the main menu...")


def manage_server_menu(ctx: click.Context, server_name: str):
    """Displays the menu for managing a specific, existing server.

    This menu is built dynamically based on the host system's capabilities,
    ensuring that only relevant options are presented to the user.

    Args:
        ctx: The current click command context.
        server_name: The name of the server being managed.
    """
    cli = ctx.obj["cli"]
    bsm: BedrockServerManager = ctx.obj["bsm"]

    def get_cmd(group_name, cmd_name):
        """Helper to safely retrieve a command object from the CLI."""
        group = cli.get_command(ctx, group_name)
        return group.get_command(ctx, cmd_name) if group else None

    # ---- Define static menu sections ----
    control_map = {
        "Start Server": (get_cmd("server", "start"), {}),
        "Stop Server": (get_cmd("server", "stop"), {}),
        "Restart Server": (get_cmd("server", "restart"), {}),
        "Send Command to Server": (get_cmd("server", "send-command"), {}),
    }
    management_map = {
        "Backup or Restore": _backup_restore_menu,
        "Manage World": _world_management_menu,
        "Install Addon": (cli.get_command(ctx, "install-addon"), {}),
    }
    config_map = {
        "Configure Properties": (get_cmd("properties", "set"), {}),
        "Configure Allowlist": (get_cmd("allowlist", "add"), {}),
        "Configure Permissions": (get_cmd("permissions", "set"), {}),
    }
    maintenance_map = {
        "Update Server": (get_cmd("server", "update"), {}),
        "Delete Server": (get_cmd("server", "delete"), {}),
    }

    # ---- Dynamically build the system menu based on capabilities ----
    system_map = {}
    if bsm.can_manage_services:
        system_map["Configure System Service"] = (
            get_cmd("system", "configure-service"),
            {},
        )

    system_map["Monitor Resource Usage"] = (get_cmd("system", "monitor"), {})

    if bsm.can_schedule_tasks:
        system_map["Schedule Tasks (cron/schtasks)"] = cli.get_command(ctx, "schedule")

    if bsm.get_os_type() == "Linux":
        system_map["Attach to Console"] = (cli.get_command(ctx, "attach-console"), {})

    # ---- Combine all maps for easy lookup ----
    full_menu_map = {
        **control_map,
        **management_map,
        **config_map,
        **system_map,
        **maintenance_map,
        "Back to Main Menu": "back",
    }

    # ---- Build the final choices list for questionary ----
    menu_choices = [
        Separator("--- Server Control ---"),
        *control_map.keys(),
        Separator("--- Management ---"),
        *management_map.keys(),
        Separator("--- Configuration ---"),
        *config_map.keys(),
    ]

    if system_map:  # Only show this section if there are system commands available
        menu_choices.extend(
            [Separator("--- System & Monitoring ---"), *system_map.keys()]
        )

    menu_choices.extend(
        [
            Separator("--- Maintenance ---"),
            *maintenance_map.keys(),
            Separator("--------------------"),
            "Back to Main Menu",
        ]
    )

    while True:
        click.clear()
        click.secho(f"--- Managing Server: {server_name} ---", fg="magenta", bold=True)
        ctx.invoke(list_servers, server_name=server_name)

        choice = questionary.select(
            f"\nSelect an action for '{server_name}':",
            choices=menu_choices,
            use_indicator=True,
        ).ask()

        if choice is None or choice == "Back to Main Menu":
            return

        action = full_menu_map.get(choice)
        if not action:
            continue

        try:
            if callable(action) and not hasattr(action, "commands"):
                action(ctx, server_name)
            elif isinstance(action, tuple):
                command_obj, kwargs = action
                if not command_obj:
                    continue
                if command_obj.name == "send-command":
                    cmd_str = questionary.text("Enter command to send:").ask()
                    if cmd_str:
                        kwargs["command_parts"] = cmd_str.split()
                    else:
                        continue
                kwargs["server_name"] = server_name
                ctx.invoke(command_obj, **kwargs)
                if command_obj.name == "delete":
                    click.echo("\nServer has been deleted. Returning to main menu.")
                    click.pause()
                    return
            elif hasattr(action, "commands"):
                ctx.invoke(action, server_name=server_name)

            click.pause("\nPress any key to return to the server menu...")

        except Exception as e:
            logger.error(f"Server menu error for action '{choice}': {e}", exc_info=True)
            click.secho(f"An error occurred while executing '{choice}': {e}", fg="red")
            click.pause()
