import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from ...api import permissions as permissions_api
from ...context import AppContext
from ...error import BSMError, UserInputError
from ..deps import get_app_context, get_moderator_user, validate_server_exists
from ..schemas import (
    PermissionsGetResponse,
    PermissionsSetPayload,
    PermissionsUpdateResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(
    tags=["Player Management", "Server Management", "Permissions Management"],
)


@router.post(
    "/api/server/{server_name}/permissions/set",
    response_model=PermissionsUpdateResponse,
    status_code=status.HTTP_200_OK,
)
async def post_permissions_set(
    payload: PermissionsSetPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    permission_entries = payload.permissions
    errors: Dict[str, str] = {}
    success_count = 0

    for item in permission_entries:
        try:
            result = permissions_api.set_permissions(
                server_name=server_name,
                xuid=item.xuid,
                player_name=item.name,
                permission=item.permission_level,
                app_context=app_context,
            )
            if result.get("status") == "success":
                success_count += 1
            else:
                errors[item.xuid] = result.get(
                    "message", "Unknown error setting permission."
                )
        except UserInputError as e:
            errors[item.xuid] = str(e)
        except BSMError as e:
            errors[item.xuid] = str(e)
        except Exception:
            errors[item.xuid] = "An unexpected server error occurred."

    if not errors:
        return PermissionsUpdateResponse(
            status="success",
            message=f"Permissions updated for {success_count} player(s).",
        )

    final_status_code = status.HTTP_400_BAD_REQUEST
    error_values = list(errors.values())
    if any("not found" in err_msg.lower() for err_msg in error_values):
        final_status_code = status.HTTP_404_NOT_FOUND
    is_internal_server_error = any(
        "unexpected" in err_msg.lower() or "bsmerror" in err_msg.lower()
        for err_msg in error_values
    )
    if is_internal_server_error:
        final_status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    return JSONResponse(
        status_code=final_status_code,
        content=PermissionsUpdateResponse(
            status="error",
            message="Errors occurred setting permissions.",
            errors=errors,
        ).model_dump(),
    )


@router.get(
    "/api/server/{server_name}/permissions/get",
    response_model=PermissionsGetResponse,
)
async def get_permissions(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    result = permissions_api.get_permissions(
        server_name=server_name, app_context=app_context
    )
    if result.get("status") == "success":
        return PermissionsGetResponse(
            status=result["status"], permissions=result.get("permissions", [])
        )
    if "not found" in result.get("message", "").lower():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message")
        )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=result.get("message", "Failed to get server permissions."),
    )
