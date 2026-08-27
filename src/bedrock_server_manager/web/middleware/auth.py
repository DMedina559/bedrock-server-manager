from fastapi import Request

from ..deps.auth import get_current_user_optional


async def add_user_to_request(request: Request, call_next):
    """
    Middleware that checks for a valid authentication token/cookie and adds
    the current user to `request.state.current_user`.
    """
    user = await get_current_user_optional(request)
    request.state.current_user = user
    response = await call_next(request)
    return response
