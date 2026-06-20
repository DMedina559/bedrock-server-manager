import logging

from fastapi import APIRouter, Depends, HTTPException, status

from ...api import allowlist as allowlist_api
from ...context import AppContext
from ...error import BSMError, UserInputError
from ..auth_utils import get_moderator_user
from ..dependencies import get_app_context, validate_server_exists
from ..schemas import (
    AllowlistAddPayload,
    AllowlistGetResponse,
    AllowlistRemovePayload,
    BaseApiResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(
    tags=["Allowlist Management", "Player Management", "Server Management"],
)


@router.post(
    "/api/server/{server_name}/allowlist/add",
    response_model=BaseApiResponse,
    status_code=status.HTTP_200_OK,
)
async def post_allowlist(
    payload: AllowlistAddPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    identity = current_user.username
    logger.info(
        f"API: Add to allowlist request for '{server_name}' by user '{identity}'. Players: {payload.players}"
    )
    new_players_data = [
        {"name": p, "ignoresPlayerLimit": payload.ignoresPlayerLimit}
        for p in payload.players
    ]
    try:
        result = allowlist_api.add_to_allowlist(
            server_name=server_name,
            new_players_data=new_players_data,
            app_context=app_context,
        )
        if result.get("status") == "success":
            return BaseApiResponse(
                status=result["status"], message=result.get("message")
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("message", "Failed to add players."),
        )
    except UserInputError as e:
        _ = e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        _ = e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )


@router.get(
    "/api/server/{server_name}/allowlist/get",
    response_model=AllowlistGetResponse,
)
async def get_allowlist(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    result = allowlist_api.get_allowlist(
        server_name=server_name, app_context=app_context
    )
    if result.get("status") == "success":
        return AllowlistGetResponse(
            status=result["status"], players=result.get("players", [])
        )
    if "not found" in result.get("message", "").lower():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message")
        )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=result.get("message", "Failed to get allowlist."),
    )


@router.delete(
    "/api/server/{server_name}/allowlist/remove",
    response_model=BaseApiResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_allowlist(
    payload: AllowlistRemovePayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    try:
        result = allowlist_api.remove_from_allowlist(
            server_name=server_name,
            player_names=payload.players,
            app_context=app_context,
        )
        if result.get("status") == "success":
            return BaseApiResponse(
                status=result["status"], message=result.get("message")
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("message", "Failed to remove players."),
        )
    except UserInputError as e:
        _ = e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        _ = e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected server error occurred.",
        )
