import logging

from fastapi import APIRouter, Depends, HTTPException, status

from bedrock_server_manager.api.models import (
    GetPropertiesRequest,
    SetPropertiesRequest,
)

from ...api import properties as properties_api
from ...context import AppContext
from ...error import AppFileNotFoundError, BSMError, UserInputError
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
    operation_id="set_properties",
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
        result = await properties_api.set_properties(
            request=SetPropertiesRequest(
                server_name=server_name, properties_to_update=properties_data
            ),
            app_context=app_context,
        )
        if result.status == "success":
            return BaseApiResponse(status=result.status, message=result.message)
        if (
            "not found" in result.message.lower()
            or "invalid server" in result.message.lower()
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=result.message
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=result.message
        )
    except UserInputError as e:
        _ = e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
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
    "/api/server/{server_name}/properties/get",
    operation_id="get_properties",
    response_model=PropertiesGetResponse,
)
async def get_properties(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    result = await properties_api.get_properties(
        request=GetPropertiesRequest(server_name=server_name),
        app_context=app_context,
    )
    if result.status == "success":
        return PropertiesGetResponse(
            status=result.status,
            properties=result.properties,
            raw_content=result.raw_content,
        )
    if "not found" in result.message.lower():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=result.message
        )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=result.message,
    )
