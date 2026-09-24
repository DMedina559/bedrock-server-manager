from fastapi import Request

from ..deps.auth import get_current_user_optional


async def add_user_to_request(request: Request, call_next):
    """
    Middleware that checks for a valid authentication token/cookie and adds
    the current user to `request.state.current_user`.
    """

    # 1. Bypass database lookup for static files to prevent SQLite locking
    if (
        request.url.path.startswith(
            ("/static", "/assets", "/image", "/app/static", "/app/assets", "/app/image")
        )
        or request.url.path == "/favicon.ico"
    ):
        request.state.current_user = None
        return await call_next(request)

    # 2. Normal auth lookup for API and Page requests
    user = await get_current_user_optional(request)
    request.state.current_user = user

    response = await call_next(request)
    return response
