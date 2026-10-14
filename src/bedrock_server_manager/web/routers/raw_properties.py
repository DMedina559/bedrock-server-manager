"""Read-only raw server.properties document endpoint."""

from fastapi import APIRouter, Depends

from ...api import properties as properties_api
from ...api.models import GetRawPropertiesRequest, GetRawPropertiesResponse
from ...context import AppContext
from ..deps import get_app_context, get_moderator_user, validate_server_exists
from ..schemas import UserResponse

router = APIRouter(tags=["Server Raw Properties"])


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
