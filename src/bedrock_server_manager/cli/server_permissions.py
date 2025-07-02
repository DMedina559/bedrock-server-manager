# bedrock_server_manager/cli/server_permissions.py
"""
Defines the `bsm permissions` command group for managing player permission levels.

This module provides CLI tools to view and set player permission levels
(e.g., member, operator, visitor) for a specific Bedrock server. These
permissions are typically stored in the server's ``permissions.json`` file.

The commands interact with the API layer, specifically functions in
:mod:`~bedrock_server_manager.api.server_install_config` for getting and
setting permissions, and :mod:`~bedrock_server_manager.api.player` for
looking up player XUIDs from the global player database.

Key functionalities:

    -   An interactive workflow (:func:`~.interactive_permissions_workflow`) to
        guide users through selecting a player and assigning a permission level.
    -   Direct commands (``bsm permissions set``, ``bsm permissions list``) for
        scripting or quick modifications.

"""
from typing import Optional

import click
import questionary

from bedrock_server_manager.api import player as player_api
from bedrock_server_manager.api import server_install_config as config_api
from bedrock_server_manager.cli.utils import (
    handle_api_response as _handle_api_response,
)
from bedrock_server_manager.error import BSMError


def interactive_permissions_workflow(server_name: str):
    """
    Guides the user through an interactive workflow to set a player's permission level.

    This function performs the following steps:

        1.  Fetches all known players from the global player database using
            :func:`~bedrock_server_manager.api.player.get_all_known_players_api`.
        2.  If no players are found, it informs the user and suggests commands to
            populate the database.
        3.  Prompts the user to select a player from the list using `questionary`.
        4.  Prompts the user to select a permission level (member, operator, visitor)
            for the chosen player.
        5.  Calls :func:`~bedrock_server_manager.api.server_install_config.configure_player_permission`
            to apply the selected permission to the specified server.
        6.  Uses :func:`~.handle_api_response` to display the outcome.

    Args:
        server_name (str): The name of the server for which to configure permissions.

    Raises:
        click.Abort: If the user cancels the operation at any `questionary` prompt
                     (e.g., by pressing Ctrl+C).
    """
    click.secho("\n--- Interactive Permission Configuration ---", bold=True)
    player_response = player_api.get_all_known_players_api()
    all_players = player_response.get("players", [])

    if not all_players:
        click.secho(
            "No players found in the global player database (players.json).",
            fg="yellow",
        )
        click.secho(
            "Run 'bsm player scan' or 'bsm player add' to populate it first.", fg="cyan"
        )
        return

    # Create a user-friendly mapping for the selection prompt
    player_map = {f"{p['name']} (XUID: {p['xuid']})": p for p in all_players}
    choices = sorted(list(player_map.keys())) + ["Cancel"]

    player_choice_str = questionary.select(
        "Select a player to configure permissions for:", choices=choices
    ).ask()

    if not player_choice_str or player_choice_str == "Cancel":
        raise click.Abort()

    selected_player = player_map[player_choice_str]
    permission = questionary.select(
        f"Select permission level for {selected_player['name']}:",
        choices=["member", "operator", "visitor"],
        default="member",
    ).ask()

    if permission is None:  # User pressed Ctrl+C
        raise click.Abort()

    perm_response = config_api.configure_player_permission(
        server_name, selected_player["xuid"], selected_player["name"], permission
    )
    _handle_api_response(
        perm_response,
        f"Permission for {selected_player['name']} set to '{permission}'.",
    )


@click.group()
def permissions():
    """
    Manages player permission levels (e.g., operator, member) on a server.

    These commands interact with the server's `permissions.json` file.
    """
    pass


@permissions.command("set")
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="The name of the target server.",
)
@click.option(
    "-p",
    "--player",
    "player_name",
    help="The gamertag of the player. Skips interactive mode.",
)
@click.option(
    "-l",
    "--level",
    type=click.Choice(["visitor", "member", "operator"], case_sensitive=False),
    help="The permission level to grant. Skips interactive mode.",
)
def set_perm(server_name: str, player_name: Optional[str], level: Optional[str]):
    """
    Sets a permission level for a player on a specific server.

    If both `--player` and `--level` options are provided, this command directly
    attempts to set the permission. It first looks up the player's XUID from the
    global player database using their gamertag.

    If either `--player` or `--level` is omitted, the command falls back to an
    interactive workflow (:func:`~.interactive_permissions_workflow`) to guide
    the user through selecting a player and permission level.

    Permission levels are typically 'visitor', 'member', or 'operator'.

    Calls APIs:
        - :func:`~bedrock_server_manager.api.player.get_all_known_players_api` (for XUID lookup)
        - :func:`~bedrock_server_manager.api.server_install_config.configure_player_permission`
    """
    try:
        if not player_name or not level:
            click.secho(
                f"Player or level not specified; starting interactive editor for '{server_name}'...",
                fg="yellow",
            )
            interactive_permissions_workflow(server_name)
            return

        # Direct, non-interactive logic
        click.echo(f"Finding player '{player_name}' in global database...")
        all_players_resp = player_api.get_all_known_players_api()
        player_data = next(
            (
                p
                for p in all_players_resp.get("players", [])
                if p.get("name", "").lower() == player_name.lower()
            ),
            None,
        )

        if not player_data or not player_data.get("xuid"):
            click.secho(
                f"Error: Player '{player_name}' not found in the global player database.",
                fg="red",
            )
            click.secho(
                "Run 'bsm player add' or 'bsm player scan' to add them first.",
                fg="cyan",
            )
            raise click.Abort()

        xuid = player_data["xuid"]
        click.echo(
            f"Setting permission for {player_name} (XUID: {xuid}) to '{level}'..."
        )
        response = config_api.configure_player_permission(
            server_name, xuid, player_name, level
        )
        _handle_api_response(response, "Permission updated successfully.")

    except (click.Abort, KeyboardInterrupt, BSMError):
        click.secho("\nOperation cancelled.", fg="yellow")


@permissions.command("list")
@click.option(
    "-s", "--server", "server_name", required=True, help="The name of the server."
)
def list_perms(server_name: str):
    """
    Lists all configured player permissions for a specific server.

    Retrieves and displays the contents of the server's `permissions.json` file,
    showing each player's gamertag (if known from the global player DB), XUID,
    and their assigned permission level (e.g., Operator, Member).

    Permission levels are color-coded for readability.

    Calls API: :func:`~bedrock_server_manager.api.server_install_config.get_server_permissions_api`.
    """
    response = config_api.get_server_permissions_api(server_name)

    # Handle API errors first
    if response.get("status") == "error":
        _handle_api_response(response, "")
        return

    permissions = response.get("data", []).get("permissions", [])

    if not permissions:
        click.secho(
            f"The permissions file for server '{server_name}' is empty or does not exist.",
            fg="yellow",
        )
        return

    click.secho(f"\nPermissions for '{server_name}':", bold=True)
    for p in permissions:
        # Use styled output for permission levels for better readability
        level = p.get(
            "permission_level", "unknown"
        ).lower()  # API used `permission_level` before, now `permission`
        level_color = {"operator": "red", "member": "green", "visitor": "blue"}.get(
            level, "white"
        )
        level_styled = click.style(level.capitalize(), fg=level_color, bold=True)

        name = p.get("name", "Unknown Player")
        xuid = p.get("xuid", "N/A")
        click.echo(f"  - {name:<20} (XUID: {xuid:<18}) {level_styled}")
