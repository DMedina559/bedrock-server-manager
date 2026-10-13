"""Core player notifications do not require the plugin API facade."""

from typing import Literal, Self

from pydantic import Field, model_validator

from .models import EventDefinition, EventModel, EventRecord
from .publisher import EventPublisher
from .registry import builtin_events


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


class PlayerChangeResult(PlayerSnapshot):
    status: Literal["success"] = "success"
    message: str | None = None


class BeforePlayerChange(PlayerSnapshot):
    request: PlayerSnapshot


class AfterPlayerChange(BeforePlayerChange):
    result: PlayerChangeResult


for name, phase, model in (
    ("before_server_players_change", "before", BeforePlayerChange),
    ("after_server_players_change", "after", AfterPlayerChange),
):
    builtin_events.register(
        EventDefinition(name=name, phase=phase), model, allow_variants=True
    )


async def publish_player_snapshot(
    events: EventPublisher, snapshot: PlayerSnapshot
) -> EventRecord:
    """Return the receipt so callers can retry dispatch rejected before delivery."""
    data = snapshot.model_dump(mode="json")
    data["request"] = snapshot
    data["result"] = PlayerChangeResult(**snapshot.model_dump())
    return await events.emit("after_server_players_change", data)
