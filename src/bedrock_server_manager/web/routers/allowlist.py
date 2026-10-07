import logging

from fastapi import APIRouter, Depends, HTTPException, status

from bedrock_server_manager.api.models import (
    AddToAllowlistRequest,
    GetAllowlistRequest,
    RemoveFromAllowlistRequest,
)

from ...api import allowlist as allowlist_api
from ...context import AppContext
from ...error import AppFileNotFoundError, BSMError, UserInputError
from ..deps import get_app_context, get_moderator_user, validate_server_exists
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
    operation_id="add_allowlist_players",
    response_model=BaseApiResponse,
    status_code=status.HTTP_200_OK,
)
async def post_allowlist(
    payload: AllowlistAddPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> BaseApiResponse:
    identity = current_user.username
    logger.info(
        f"API: Add to allowlist request for '{server_name}' by user '{identity}'. Players: {payload.players}"
    )
    new_players_data = [
        {"name": p, "ignoresPlayerLimit": payload.ignoresPlayerLimit}
        for p in payload.players
    ]
    try:
        result = await allowlist_api.add_to_allowlist(
            request=AddToAllowlistRequest.model_validate(
                {"server_name": server_name, "new_players_data": new_players_data}
            ),
            app_context=app_context,
        )
        return BaseApiResponse(status=result.status, message=result.message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.message,
        )
    except UserInputError as e:
        _ = e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except AppFileNotFoundError:
        raise
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
    operation_id="get_allowlist",
    response_model=AllowlistGetResponse,
)
async def get_allowlist(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> AllowlistGetResponse:
    result = await allowlist_api.get_allowlist(
        request=GetAllowlistRequest.model_validate({"server_name": server_name}),
        app_context=app_context,
    )
    return result


@router.delete(
    "/api/server/{server_name}/allowlist/remove",
    operation_id="remove_allowlist_players",
    response_model=BaseApiResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_allowlist(
    payload: AllowlistRemovePayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> BaseApiResponse:
    try:
        result = await allowlist_api.remove_from_allowlist(
            request=RemoveFromAllowlistRequest.model_validate(
                {"server_name": server_name, "player_names": payload.players}
            ),
            app_context=app_context,
        )
        return BaseApiResponse(status=result.status, message=result.message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.message,
        )
    except UserInputError as e:
        _ = e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except AppFileNotFoundError:
        raise
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
