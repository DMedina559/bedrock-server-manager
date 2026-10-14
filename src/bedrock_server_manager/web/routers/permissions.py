import logging
from typing import Dict

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from bedrock_server_manager.api.models import (
    GetPermissionsRequest,
    SetPermissionsRequest,
)

from ...api import permissions as permissions_api
from ...api.models.common import APIErrorResponse, ErrorEnvelope
from ...context import AppContext
from ...failures import classify_failure
from ...logging import log_operation_error
from ...results import CompletedItem, FailedItem, ItemResult, SkippedItem
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
    failures = []
    outcomes: dict[str, ItemResult] = {}

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
                outcomes[item.xuid] = CompletedItem(outcome="completed")
            else:
                outcomes[item.xuid] = SkippedItem(
                    outcome="skipped", reason=result.message
                )
        except Exception as error:
            failure = classify_failure(error)
            failures.append(failure)
            errors[item.xuid] = failure.error.message
            outcomes[item.xuid] = FailedItem(outcome="failed", error=failure.error)
            if not failure.expected:
                log_operation_error(
                    logger, "Permission update failed for %s", item.xuid, error=error
                )

    if not failures:
        skipped = any(item.outcome == "skipped" for item in outcomes.values())
        return PermissionsUpdateResponse(
            status=(
                "partial"
                if skipped and success_count
                else "skipped" if skipped else "success"
            ),
            message=f"Permissions updated for {success_count} player(s).",
            updated=success_count,
            outcomes=outcomes,
        )
    primary = max(
        failures,
        key=lambda failure: {
            500: 6,
            503: 7,
            409: 5,
            404: 4,
            403: 3,
            422: 2,
            400: 1,
        }.get(failure.status_code, 0),
    )
    return JSONResponse(
        status_code=primary.status_code,
        content=ErrorEnvelope(
            error=APIErrorResponse(
                code=primary.error.code,
                message="Errors occurred setting permissions.",
                details={
                    "errors": {key: value for key, value in errors.items()},
                    "updated": success_count,
                    "outcomes": {
                        key: value.model_dump(mode="json")
                        for key, value in outcomes.items()
                    },
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
