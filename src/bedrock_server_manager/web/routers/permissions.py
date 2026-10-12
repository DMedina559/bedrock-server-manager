import logging
from typing import Dict

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from bedrock_server_manager.api.models import (
    GetPermissionsRequest,
    SetPermissionsRequest,
)

from ...api import permissions as permissions_api
from ...api.errors import error_response, error_status_code
from ...api.models.common import APIErrorResponse, ErrorEnvelope
from ...context import AppContext
from ...logging import log_operation_error
from ..deps import get_app_context, get_moderator_user, validate_server_exists
from ..schemas import (
    PermissionsGetResponse,
    PermissionsSetPayload,
    PermissionsUpdateResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Server Access"])


@router.post(
    "/api/server/{server_name}/permissions/set",
    operation_id="set_permissions",
    response_model=PermissionsUpdateResponse,
    status_code=status.HTTP_200_OK,
)
async def post_permissions_set(
    payload: PermissionsSetPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> PermissionsUpdateResponse | JSONResponse:
    permission_entries = payload.permissions
    errors: Dict[str, str] = {}
    success_count = 0
    error_statuses: list[int] = []

    for item in permission_entries:
        try:
            result = await permissions_api.set_permissions(
                request=SetPermissionsRequest.model_validate(
                    {
                        "server_name": server_name,
                        "xuid": item.xuid,
                        "player_name": item.name,
                        "permission": item.permission_level,
                    }
                ),
                app_context=app_context,
            )
            if result.status == "success":
                success_count += 1
            else:
                errors[item.xuid] = result.message
        except Exception as error:
            errors[item.xuid] = error_response(error).message
            error_statuses.append(error_status_code(error))
            if error_statuses[-1] == 500:
                log_operation_error(
                    logger, "Permission update failed for %s", item.xuid, error=error
                )

    if not errors:
        return PermissionsUpdateResponse(
            status="success",
            message=f"Permissions updated for {success_count} player(s).",
        )

    final_status_code = next(
        (code for code in (500, 409, 404, 403, 422, 400) if code in error_statuses),
        400,
    )

    return JSONResponse(
        status_code=final_status_code,
        content=ErrorEnvelope(
            error=APIErrorResponse(
                code=(
                    "internal_error"
                    if final_status_code == 500
                    else (
                        "conflict"
                        if final_status_code == 409
                        else (
                            "not_found"
                            if final_status_code == 404
                            else (
                                "forbidden"
                                if final_status_code == 403
                                else "validation_error"
                            )
                        )
                    )
                ),
                message="Errors occurred setting permissions.",
                details={
                    "errors": {key: value for key, value in errors.items()},
                    "updated": success_count,
                },
            )
        ).model_dump(mode="json"),
    )


@router.get(
    "/api/server/{server_name}/permissions/get",
    operation_id="get_permissions",
    response_model=PermissionsGetResponse,
)
async def get_permissions(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> PermissionsGetResponse:
    result = await permissions_api.get_permissions(
        request=GetPermissionsRequest.model_validate({"server_name": server_name}),
        app_context=app_context,
    )
    return result
