"""Core player notifications do not require the plugin API facade."""

from typing import Self

from pydantic import Field, model_validator

from ..state_revision import revision_clock
from .models import EventModel


class PlayerPresence(EventModel):
    name: str = Field(min_length=1)
    xuid: str = Field(min_length=1)


class PlayerSnapshot(EventModel):
    server_name: str = Field(min_length=1)
    player_count: int = Field(ge=0)
    players: list[PlayerPresence]

    @model_validator(mode="after")
    def coherent_count(self) -> Self:
        if self.player_count != len(self.players):
            raise ValueError("Player count must match the player list")
        return self


async def publish_player_snapshot(
    context, *, server_name: str, player_count: int, players: list[dict]
) -> None:
    snapshot = PlayerSnapshot(
        server_name=server_name, player_count=player_count, players=players
    )
    data = snapshot.model_dump(mode="json")
    # State is already authoritative; this is an after-operation notification.
    data["result"] = {"status": "success", "message": None, **data}
    data["request"] = snapshot.model_dump(mode="json")
    await context.events.emit(
        "after_server_players_change", data, revision=dict(revision_clock.capture())
    )
