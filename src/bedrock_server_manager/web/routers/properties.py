import logging

from fastapi import APIRouter, Depends, HTTPException, Security, status

from ...api import properties as properties_api
from ...context import AppContext
from ...models import (
    GetPropertiesRequest,
    GetPropertiesResponse,
    GetRawPropertiesRequest,
    GetRawPropertiesResponse,
    PropertiesPayload,
    SetPropertiesRequest,
    SetPropertiesResponse,
)
from ..access_policy import Permission
from ..deps import get_app_context, validate_server_exists
from ..deps.auth import require_permissions
from ..schemas import UserResponse

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
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.PROPERTIES_MANAGE]
    ),
    server_name: str = Depends(validate_server_exists),
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
    response_model=GetPropertiesResponse,
)
async def get_properties(
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.PROPERTIES_READ]
    ),
    server_name: str = Depends(validate_server_exists),
    app_context: AppContext = Depends(get_app_context),
) -> GetPropertiesResponse:
    return await properties_api.get_properties(
        request=GetPropertiesRequest(server_name=server_name),
        app_context=app_context,
    )


@router.get(
    "/api/server/{server_name}/properties/raw",
    operation_id="get_raw_properties",
    response_model=GetRawPropertiesResponse,
)
async def get_raw_properties(
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.PROPERTIES_READ]
    ),
    server_name: str = Depends(validate_server_exists),
    app_context: AppContext = Depends(get_app_context),
) -> GetRawPropertiesResponse:
    """Return the raw document using the same access policy as structured properties."""
    return await properties_api.get_raw_properties(
        request=GetRawPropertiesRequest(server_name=server_name),
        app_context=app_context,
    )
