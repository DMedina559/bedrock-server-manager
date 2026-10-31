"""FastAPI router for central player database management."""

import logging

from fastapi import APIRouter, Depends, Security

from bedrock_server_manager.api.models import (
    AddPlayersManuallyRequest,
    GetAllKnownPlayersRequest,
    ScanAndUpdatePlayerDbRequest,
)

from ...api import player as player_api
from ...context import AppContext
from ..access_policy import Permission
from ..deps import get_app_context
from ..deps.auth import require_permissions
from ..schemas import (
    AddPlayersPayload,
    AddPlayersResponse,
    PlayerListResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.put(
    "/api/players/scan",
    operation_id="scan_players",
    tags=["Player Management"],
    response_model=AddPlayersResponse,
)
async def put_scan_players(
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.PLAYERS_MANAGE]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> AddPlayersResponse:
    """
    Scans all server logs to discover and update the central player database.
    """
    identity = current_user.username
    logger.info("Request to scan logs for players by user '%s'.", identity)
    result = await player_api.scan_and_update_player_db(
        request=ScanAndUpdatePlayerDbRequest(), app_context=app_context
    )
    return AddPlayersResponse(
        status="success",
        message=result.message,
        details=result.details,
    )


@router.get(
    "/api/players/get",
    operation_id="list_players",
    tags=["Player Management"],
    response_model=PlayerListResponse,
)
async def get_all_players(
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.PLAYERS_READ]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> PlayerListResponse:
    """Return the list of all known players from the central player database."""
    identity = current_user.username
    logger.debug("Request to retrieve all players by user '%s'.", identity)
    result_dict = await player_api.get_all_known_players(
        request=GetAllKnownPlayersRequest(), app_context=app_context
    )

    logger.debug(
        "API Get All Players: Successfully retrieved %s players. Message: %s",
        len(result_dict.players),
        result_dict.message,
    )
    return PlayerListResponse(
        status="success",
        players=result_dict.players,
        message=result_dict.message,
    )


@router.post(
    "/api/players/add",
    operation_id="add_players",
    tags=["Player Management"],
    response_model=AddPlayersResponse,
)
async def post_add_players(
    payload: AddPlayersPayload,
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.PLAYERS_MANAGE]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> AddPlayersResponse:
    """
    Manually adds or updates player entries in the central player database.
    """
    identity = current_user.username
    logger.info(
        "Player registration requested by user '%s' (%s entries).",
        identity,
        len(payload.players),
    )
    result = await player_api.add_players_manually(
        request=AddPlayersManuallyRequest(player_strings=payload.players),
        app_context=app_context,
    )

    return AddPlayersResponse(
        status="success",
        message=result.message,
        count=result.count,
        submitted_count=result.submitted_count,
        parsed_count=result.parsed_count,
        unique_count=result.unique_count,
    )
