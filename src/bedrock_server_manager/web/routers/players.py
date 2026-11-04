"""FastAPI router for central player database management."""

import logging

from fastapi import APIRouter, Depends, Security

from bedrock_server_manager.api.models import (
    AddPlayersManuallyRequest,
    AddPlayersManuallyResponse,
    GetAllKnownPlayersRequest,
    GetAllKnownPlayersResponse,
    ScanAndUpdatePlayerDbRequest,
    ScanAndUpdatePlayerDbResponse,
)

from ...api import player as player_api
from ...context import AppContext
from ..access_policy import Permission
from ..deps import get_app_context
from ..deps.auth import require_permissions
from ..schemas import (
    AddPlayersPayload,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.put(
    "/api/players/scan",
    operation_id="scan_players",
    tags=["Player Management"],
    response_model=ScanAndUpdatePlayerDbResponse,
)
async def put_scan_players(
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.PLAYERS_MANAGE]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> ScanAndUpdatePlayerDbResponse:
    """
    Scans all server logs to discover and update the central player database.
    """
    identity = current_user.username
    logger.info("Request to scan logs for players by user '%s'.", identity)
    return await player_api.scan_and_update_player_db(
        request=ScanAndUpdatePlayerDbRequest(), app_context=app_context
    )


@router.get(
    "/api/players/get",
    operation_id="list_players",
    tags=["Player Management"],
    response_model=GetAllKnownPlayersResponse,
)
async def get_all_players(
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.PLAYERS_READ]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> GetAllKnownPlayersResponse:
    """Return the list of all known players from the central player database."""
    identity = current_user.username
    logger.debug("Request to retrieve all players by user '%s'.", identity)
    result = await player_api.get_all_known_players(
        request=GetAllKnownPlayersRequest(), app_context=app_context
    )

    logger.debug(
        "API Get All Players: Successfully retrieved %s players. Message: %s",
        len(result.players),
        result.message,
    )
    return result


@router.post(
    "/api/players/add",
    operation_id="add_players",
    tags=["Player Management"],
    response_model=AddPlayersManuallyResponse,
)
async def post_add_players(
    payload: AddPlayersPayload,
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.PLAYERS_MANAGE]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> AddPlayersManuallyResponse:
    """
    Manually adds or updates player entries in the central player database.
    """
    identity = current_user.username
    logger.info(
        "Player registration requested by user '%s' (%s entries).",
        identity,
        len(payload.players),
    )
    return await player_api.add_players_manually(
        request=AddPlayersManuallyRequest(player_strings=payload.players),
        app_context=app_context,
    )
