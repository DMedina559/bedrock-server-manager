# bedrock_server_manager/cli/player.py
"""
Defines the `bsm player` command group for managing the global player database.

This module provides CLI tools to interact with the central player database
(typically ``players.json``), which stores mappings between player gamertags
and their Xbox User IDs (XUIDs). This information is essential for features
like allowlists and permissions that rely on XUIDs.

Commands allow for:
    -   Scanning all server logs to automatically discover players and their XUIDs.
    -   Manually adding or updating player entries in the database.
    -   (Future potential: Listing all known players).

These commands primarily call functions from the
:mod:`~bedrock_server_manager.api.player` module.
"""

import logging
from typing import Tuple

import click

from bedrock_server_manager.api import player as player_api
from bedrock_server_manager.cli.utils import handle_api_response as _handle_api_response
from bedrock_server_manager.error import BSMError

logger = logging.getLogger(__name__)


@click.group()
def player():
    """
    Manages the central player database (linking gamertags to XUIDs).

    This database is used by other features like permissions and allowlisting
    to identify players by their unique Xbox User ID (XUID) even if only
    a gamertag is initially known.
    """
    pass


@player.command("scan")
def scan_for_players():
    """
    Scans all server logs to discover player gamertags and XUIDs.

    This command iterates through the log files of all configured and valid
    Bedrock server instances. It looks for player connection messages to
    extract gamertag-XUID pairs. Discovered information is then used to
    update the central player database (`players.json`).

    This is useful for automatically populating the player database without
    manual entry.

    Calls API: :func:`~bedrock_server_manager.api.player.scan_and_update_player_db_api`.
    """
    try:
        click.echo("Scanning all server logs for player data...")
        logger.debug("CLI: Calling player_api.scan_and_update_player_db_api")

        response = player_api.scan_and_update_player_db_api()
        _handle_api_response(response, "Player database updated successfully.")

    except BSMError as e:
        click.secho(f"An error occurred during scan: {e}", fg="red")
        raise click.Abort()
    except Exception as e:
        # Catch any other unexpected errors during file I/O or processing.
        click.secho(f"An unexpected error occurred: {e}", fg="red")
        raise click.Abort()


@player.command("add")
@click.option(
    "-p",
    "--player",
    "players",
    multiple=True,
    required=True,
    help="Player to add in 'Gamertag:XUID' format. Use multiple times for multiple players.",
)
def add_players(players: Tuple[str]):
    """
    Manually adds or updates player entries in the central player database.

    Each player must be specified in the "Gamertag:XUID" format.
    If a player with the given XUID already exists, their entry (including
    gamertag) will be updated. If the XUID is new, a new player entry is created.

    This command is useful for adding known players without needing to wait
    for them to connect to a server or for correcting existing entries.

    Calls API: :func:`~bedrock_server_manager.api.player.add_players_manually_api`.
    """
    try:
        # The API expects a list, so we convert the tuple from `multiple=True`.
        player_list = list(players)
        click.echo(f"Adding/updating {len(player_list)} player(s) in the database...")
        logger.debug(
            f"CLI: Calling player_api.add_players_manually_api with {len(player_list)} players."
        )

        response = player_api.add_players_manually_api(player_list)
        _handle_api_response(response, "Players added/updated successfully.")

    except BSMError as e:
        click.secho(f"An error occurred while adding players: {e}", fg="red")
        raise click.Abort()
    except Exception as e:
        click.secho(f"An unexpected error occurred: {e}", fg="red")
        raise click.Abort()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    player()
