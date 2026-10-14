"""Bounded history pages for the live application and server log viewers."""

from fastapi import APIRouter, Depends, HTTPException, Query

from ...context import AppContext
from ...error import InvalidServerNameError
from ...utils.server import core_validate_server_name_format
from ..deps import get_app_context, get_moderator_user
from ..log_streamer import LogHistoryPage
from ..schemas import UserResponse

router = APIRouter(prefix="/api/logs", tags=["Logs"])


@router.get("/history", response_model=LogHistoryPage, operation_id="get_log_history")
async def get_log_history(
    topic: str = Query(min_length=1, max_length=256),
    before: int | None = Query(default=None, ge=0),
    file_id: str | None = Query(default=None, max_length=64),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> LogHistoryPage:
    if topic in ("app_log", "app_logs") and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required.")
    if topic not in ("app_log", "app_logs") and not topic.startswith("server_log:"):
        raise HTTPException(status_code=400, detail="Invalid log topic.")
    if topic.startswith("server_log:"):
        server_name = topic.split(":", 1)[1]
        try:
            core_validate_server_name_format(server_name)
        except InvalidServerNameError:
            raise HTTPException(
                status_code=400, detail="Invalid server name."
            ) from None
        if app_context.state.servers.get(server_name) is None:
            raise HTTPException(status_code=404, detail="Server is unavailable.")
    try:
        return await app_context.log_streamer.read_history(topic, before, file_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Log is unavailable.") from None
    except ValueError:
        raise HTTPException(
            status_code=409, detail="Log file changed; reload the viewer."
        ) from None
