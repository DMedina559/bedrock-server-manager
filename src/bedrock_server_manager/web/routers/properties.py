import logging

from fastapi import APIRouter, Depends, HTTPException, status

from bedrock_server_manager.api.models import (
    GetPropertiesRequest,
    GetRawPropertiesRequest,
    GetRawPropertiesResponse,
    SetPropertiesRequest,
    SetPropertiesResponse,
)

from ...api import properties as properties_api
from ...context import AppContext
from ..deps import get_app_context, get_moderator_user, validate_server_exists
from ..schemas import (
    PropertiesGetResponse,
    PropertiesPayload,
    UserResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Server Properties"])


@router.post(
    "/api/server/{server_name}/properties/set",
    operation_id="set_properties",
    response_model=SetPropertiesResponse,
    status_code=status.HTTP_200_OK,
)
async def post_properties_set(
    payload: PropertiesPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> SetPropertiesResponse:
    properties_data = payload.properties
    if not isinstance(properties_data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid properties body."
        )
    result = await properties_api.set_properties(
        request=SetPropertiesRequest(
            server_name=server_name, properties_to_update=properties_data
        ),
        app_context=app_context,
    )
    return result


@router.get(
    "/api/server/{server_name}/properties/get",
    operation_id="get_properties",
    response_model=PropertiesGetResponse,
)
async def get_properties(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> PropertiesGetResponse:
    result = await properties_api.get_properties(
        request=GetPropertiesRequest(server_name=server_name),
        app_context=app_context,
    )
    return result


@router.get(
    "/api/server/{server_name}/properties/raw",
    operation_id="get_raw_properties",
    response_model=GetRawPropertiesResponse,
)
async def get_raw_properties(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> GetRawPropertiesResponse:
    """Return the raw document using the same access policy as structured properties."""
    return await properties_api.get_raw_properties(
        request=GetRawPropertiesRequest(server_name=server_name),
        app_context=app_context,
    )
