"""Bounded history pages for the live application and server log viewers."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security

from ...context import AppContext
from ...error import InvalidServerNameError
from ...utils.server import core_validate_server_name_format
from ..access_metadata import describe_access
from ..access_policy import Permission
from ..authorization import server_collection
from ..deps import get_app_context
from ..deps.auth import require_context_permission, require_permissions
from ..log_streamer import LogHistoryPage
from ..schemas import UserResponse

router = APIRouter(prefix="/api/logs", tags=["Logs"])
LOG_ACCESS = [
    {
        "condition": "topic=server_log:<server>",
        "schemes": ["OAuth2PasswordBearer", "APIKeyCookie", "IntegrationToken"],
        "permissions": [Permission.LOGS_READ],
    },
    {
        "condition": "topic=app_log or app_logs",
        "schemes": ["OAuth2PasswordBearer", "APIKeyCookie", "IntegrationToken"],
        "permissions": [Permission.LOGS_READ_APPLICATION],
    },
]


@router.get("/history", response_model=LogHistoryPage, operation_id="get_log_history")
@describe_access(
    "custom",
    authentication="required",
    additional_checks=["application-log-admin", "topic-server-access"],
    allowed_roles=["moderator", "admin"],
    credential_alternatives=LOG_ACCESS,
)
@server_collection
async def get_log_history(
    request: Request,
    topic: str = Query(min_length=1, max_length=256),
    before: int | None = Query(default=None, ge=0),
    file_id: str | None = Query(default=None, max_length=64),
    current_user: UserResponse = Security(require_permissions, scopes=[]),
    app_context: AppContext = Depends(get_app_context),
) -> LogHistoryPage:
    if topic in ("app_log", "app_logs"):
        await require_context_permission(
            request, current_user, Permission.LOGS_READ_APPLICATION
        )
    elif topic.startswith("server_log:"):
        server_name = topic.split(":", 1)[1]
        await require_context_permission(
            request, current_user, Permission.LOGS_READ, server_name
        )
        try:
            core_validate_server_name_format(server_name)
        except InvalidServerNameError:
            raise HTTPException(
                status_code=400, detail="Invalid server name."
            ) from None
        if app_context.state.servers.get(server_name) is None:
            raise HTTPException(status_code=404, detail="Server is unavailable.")
    else:
        raise HTTPException(status_code=400, detail="Invalid log topic.")
    try:
        return await app_context.log_streamer.read_history(topic, before, file_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Log is unavailable.") from None
    except ValueError:
        raise HTTPException(
            status_code=409, detail="Log file changed; reload the viewer."
        ) from None
