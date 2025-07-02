# bedrock_server_manager/cli/server_allowlist.py
"""
Defines the `bsm allowlist` command group for managing a server's player allowlist.

This module provides CLI tools to view, add, and remove players from a
specific Bedrock server's allowlist. The allowlist controls which players
are permitted to join the server. These commands interact with the server's
``allowlist.json`` file via API calls.

Key functionalities:

    -   An interactive workflow (:func:`~.interactive_allowlist_workflow`) to
        guide users through viewing the current allowlist and adding new players.
    -   Direct commands (``bsm allowlist add``, ``bsm allowlist remove``,
        ``bsm allowlist list``) for scripting or quick, non-interactive changes.

The commands call functions from
:mod:`~bedrock_server_manager.api.server_install_config` to perform
the underlying allowlist modifications.
"""

from typing import Tuple

import click
import questionary

from bedrock_server_manager.api import server_install_config as config_api
from bedrock_server_manager.cli.utils import (
    handle_api_response as _handle_api_response,
)
from bedrock_server_manager.error import BSMError


def interactive_allowlist_workflow(server_name: str):
    """
    Guides the user through an interactive session to view and add players to the allowlist.

    This workflow performs the following steps:

        1.  Fetches and displays the current allowlist for the specified server using
            :func:`~bedrock_server_manager.api.server_install_config.get_server_allowlist_api`.
        2.  Enters a loop prompting the user to enter gamertags of new players to add.
        3.  For each new player, it asks if they should ignore the player limit.
        4.  Checks for duplicate entries before queuing a player for addition.
        5.  If new players are added, it calls
            :func:`~bedrock_server_manager.api.server_install_config.add_players_to_allowlist_api`
            to save the changes.
        6.  Uses :func:`~.handle_api_response` to display the outcome of the save operation.

    Note:
        This interactive workflow currently only supports adding players. For
        removing players, the direct `bsm allowlist remove` command should be used.

    Args:
        server_name (str): The name of the server whose allowlist is being edited.

    Raises:
        click.Abort: If the user cancels the operation at any `questionary` prompt
                     (e.g., by pressing Ctrl+C).
    """
    response = config_api.get_server_allowlist_api(server_name)
    existing_players = response.get("players", [])

    click.secho("\n--- Interactive Allowlist Configuration ---", bold=True)
    if existing_players:
        click.echo("Current players in allowlist:")
        for p in existing_players:
            limit_str = (
                click.style(" (Ignores Limit)", fg="yellow")
                if p.get("ignoresPlayerLimit")
                else ""
            )
            click.echo(f"  - {p.get('name')}{limit_str}")
    else:
        click.secho("Allowlist is currently empty.", fg="yellow")

    new_players_to_add = []
    click.echo("\nEnter new players to add. Press Enter on an empty line to finish.")
    while True:
        player_name = questionary.text("Player gamertag:").ask()
        if not player_name or not player_name.strip():
            break

        # Check for duplicates before adding
        if any(
            p["name"].lower() == player_name.lower()
            for p in existing_players + new_players_to_add
        ):
            click.secho(
                f"Player '{player_name}' is already in the list. Skipping.", fg="yellow"
            )
            continue

        ignore_limit = questionary.confirm(
            f"Should '{player_name}' ignore the player limit?", default=False
        ).ask()
        new_players_to_add.append(
            {"name": player_name.strip(), "ignoresPlayerLimit": ignore_limit}
        )

    if new_players_to_add:
        click.echo("Updating allowlist with new players...")
        save_response = config_api.add_players_to_allowlist_api(
            server_name, new_players_to_add
        )
        _handle_api_response(save_response, "Allowlist updated successfully.")
    else:
        click.secho("No new players were added.", fg="cyan")


@click.group()
def allowlist():
    """
    Manages a server's player allowlist (whitelist).

    These commands allow viewing, adding, or removing players from a server's
    allowlist, which controls who can join the server. The operations modify
    the server's `allowlist.json` file.
    """
    pass


@allowlist.command("add")
@click.option(
    "-s", "--server", "server_name", required=True, help="The name of the server."
)
@click.option(
    "-p",
    "--player",
    "players",
    multiple=True,
    help="Gamertag of the player to add. Use multiple times for multiple players.",
)
@click.option(
    "--ignore-limit",
    is_flag=True,
    help="Allow player(s) to join even if the server is full.",
)
def add(server_name: str, players: Tuple[str], ignore_limit: bool):
    """
    Adds one or more players to a server's allowlist.

    If player gamertags are provided via the `--player` option, they are added
    directly with the specified `--ignore-limit` status.
    If no players are specified via options, this command launches an
    interactive workflow (:func:`~.interactive_allowlist_workflow`) to guide
    the user through viewing the current allowlist and adding new players
    with individual 'ignoresPlayerLimit' settings.

    Calls API: :func:`~bedrock_server_manager.api.server_install_config.add_players_to_allowlist_api`.
    """
    try:
        if not players:
            click.secho(
                f"No player specified; starting interactive editor for '{server_name}'...",
                fg="yellow",
            )
            interactive_allowlist_workflow(server_name)
            return

        # Direct, non-interactive logic
        player_data_list = [
            {"name": p_name, "ignoresPlayerLimit": ignore_limit} for p_name in players
        ]

        click.echo(
            f"Adding {len(player_data_list)} player(s) to allowlist for server '{server_name}'..."
        )
        response = config_api.add_players_to_allowlist_api(
            server_name, player_data_list
        )

        added_count = response.get("data", {}).get("added_count", 0)
        _handle_api_response(
            response,
            f"Successfully added {added_count} new player(s) to the allowlist.",
        )

    except (click.Abort, KeyboardInterrupt, BSMError):
        # Catch BSMError here as well to provide a consistent cancel message if it aborts.
        click.secho("\nOperation cancelled.", fg="yellow")


@allowlist.command("remove")
@click.option(
    "-s", "--server", "server_name", required=True, help="The name of the server."
)
@click.option(
    "-p",
    "--player",
    "players",
    multiple=True,
    required=True,
    help="Gamertag of the player to remove. Use multiple times for multiple players.",
)
def remove(server_name: str, players: Tuple[str]):
    """
    Removes one or more players from a server's allowlist.

    Specify players by their gamertags using one or more `--player` options.
    The command will report which players were successfully removed and which
    were not found in the allowlist.

    Calls API: :func:`~bedrock_server_manager.api.server_install_config.remove_players_from_allowlist_api`.
    """
    player_list = list(players)
    click.echo(
        f"Removing {len(player_list)} player(s) from '{server_name}' allowlist..."
    )
    response = config_api.remove_players_from_allowlist_api(
        server_name, player_list
    )  # API was `remove_players_from_allowlist`

    # Use the handler for errors, but provide custom output for success
    if response.get("status") == "error":
        _handle_api_response(response, "")  # Will print the error and abort
        return

    # API response for remove_players_from_allowlist includes "details" not "data"
    details = response.get("details", {})
    removed_players = details.get("removed", [])
    not_found_players = details.get("not_found", [])

    message = response.get("message", "Allowlist update process completed.")
    click.secho(message, fg="cyan" if not removed_players else "green")

    if removed_players:
        click.secho(
            f"\nSuccessfully removed {len(removed_players)} player(s):", fg="green"
        )
        for p_name in removed_players:
            click.echo(f"  - {p_name}")
    if not_found_players:
        click.secho(
            f"\n{len(not_found_players)} player(s) were not found in the allowlist:",
            fg="yellow",
        )
        for p_name in not_found_players:
            click.echo(f"  - {p_name}")


@allowlist.command("list")
@click.option(
    "-s", "--server", "server_name", required=True, help="The name of the server."
)
def list_players(server_name: str):
    """
    Lists all players currently on a server's allowlist.

    Displays each player's gamertag and indicates if they are configured
    to ignore the server's player limit.

    Calls API: :func:`~bedrock_server_manager.api.server_install_config.get_server_allowlist_api`.
    """
    response = config_api.get_server_allowlist_api(server_name)

    # Handle API errors first
    if response.get("status") == "error":
        _handle_api_response(
            response, ""
        )  # API response should contain the error message
        return

    # The API returns players directly under "players" key, not nested in "data"
    players = response.get("players", [])

    if not players:
        click.secho(f"The allowlist for server '{server_name}' is empty.", fg="yellow")
        return

    click.secho(f"\nAllowlist for '{server_name}':", bold=True)
    for p in players:
        limit_str = (
            click.style(" (Ignores Player Limit)", fg="yellow")
            if p.get("ignoresPlayerLimit")
            else ""
        )
        click.echo(f"  - {p.get('name')}{limit_str}")
