import logging

from fastapi import APIRouter, Depends, HTTPException, status

from ...api import properties as properties_api
from ...context import AppContext
from ...error import BSMError, UserInputError
from ..deps import get_app_context, get_moderator_user, validate_server_exists
from ..schemas import (
    BaseApiResponse,
    PropertiesGetResponse,
    PropertiesPayload,
    UserResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Properties Management", "Server Management"])


@router.post(
    "/api/server/{server_name}/properties/set",
    response_model=BaseApiResponse,
    status_code=status.HTTP_200_OK,
)
async def post_properties_set(
    payload: PropertiesPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    properties_data = payload.properties
    if not isinstance(properties_data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid properties body."
        )
    try:
        result = properties_api.set_properties(
            server_name=server_name,
            properties_to_update=properties_data,
            app_context=app_context,
        )
        if result.get("status") == "success":
            return BaseApiResponse(
                status=result["status"], message=result.get("message")
            )
        if (
            "not found" in result.get("message", "").lower()
            or "invalid server" in result.get("message", "").lower()
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message")
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("message")
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
    "/api/server/{server_name}/properties/get",
    response_model=PropertiesGetResponse,
)
async def get_properties(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    result = properties_api.get_properties(
        server_name=server_name, app_context=app_context
    )
    if result.get("status") == "success":
        return PropertiesGetResponse(
            status=result["status"], properties=result.get("properties", {})
        )
    if "not found" in result.get("message", "").lower():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message")
        )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=result.get("message", "Failed to get server properties."),
    )
