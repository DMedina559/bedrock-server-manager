"""
Repository for managing Player database entity operations.
"""

from typing import Any, Dict, List

from sqlalchemy.future import select

from ...error import UserInputError
from ..models import Player


class PlayerRepository:
    """Handles database persistence for Minecraft players."""

    def __init__(self, db: Any = None):
        self.db = db

    async def get_all_players(self, session: Any) -> List[Dict[str, str]]:
        """Retrieves all known players as a list of dicts with 'name' and 'xuid' keys."""
        result = await session.execute(select(Player))
        players = result.scalars().all()
        return [{"name": str(p.player_name), "xuid": str(p.xuid)} for p in players]

    async def save_players(
        self, session: Any, players_data: List[Dict[str, str]]
    ) -> int:
        """Saves or updates player records in the database."""
        if not isinstance(players_data, list):
            raise UserInputError("players_data must be a list.")

        updated_count = 0
        added_count = 0
        for p_data in players_data:
            if not (
                isinstance(p_data, dict)
                and "name" in p_data
                and "xuid" in p_data
                and isinstance(p_data["name"], str)
                and p_data["name"]
                and isinstance(p_data["xuid"], str)
                and p_data["xuid"]
            ):
                raise UserInputError(f"Invalid player entry format: {p_data}")

            xuid = p_data["xuid"]
            result = await session.execute(select(Player).filter_by(xuid=xuid))
            player = result.scalars().first()
            if player:
                if (
                    player.player_name != p_data["name"]
                    or player.xuid != p_data["xuid"]
                ):
                    player.player_name = p_data["name"]
                    player.xuid = p_data["xuid"]
                    updated_count += 1
            else:
                player = Player(
                    player_name=p_data["name"],
                    xuid=p_data["xuid"],
                )
                session.add(player)
                added_count += 1

        return added_count + updated_count
