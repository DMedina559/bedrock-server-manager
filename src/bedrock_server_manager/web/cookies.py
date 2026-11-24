"""Apply one session-cookie policy to setup, login, refresh, and logout."""

import datetime
from urllib.parse import quote

from jose import jwt

COOKIE_NAME = "access_token_cookie"


def cookie_options(request):
    """Use only the trusted ASGI scheme and isolate proxy-mounted instances."""
    return {
        "httponly": True,
        "secure": request.url.scheme == "https",
        "samesite": "lax",
        "path": quote(
            request.scope.get("root_path", "").rstrip("/"), safe="/-._~!$&'()*+,;=:@"
        )
        or "/",
    }


def set_session_cookie(response, request, token, *, max_age=None):
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(COOKIE_NAME, token, max_age=max_age, **cookie_options(request))


def clear_session_cookie(response, request):
    response.headers["Cache-Control"] = "no-store"
    response.delete_cookie(COOKIE_NAME, **cookie_options(request))


def is_cookie_mode(request, *, allow_existing: bool = False) -> bool:
    """Return whether the request negotiated or inherited cookie authentication."""
    header = request.headers.get("x-bsm-auth-mode")
    if header == "cookie":
        return True
    return (
        allow_existing
        and header is None
        and getattr(request.state, "credential_source", None) == "cookie"
    )


def deliver_session(
    response, request, access_token: str, *, allow_existing: bool = False
) -> tuple[str, bool]:
    """Deliver a session JWT via HttpOnly cookie or bearer response field."""
    cookie_mode = is_cookie_mode(request, allow_existing=allow_existing)
    if cookie_mode:
        claims = jwt.get_unverified_claims(access_token)
        request.state.issued_session_id = claims["sid"]
        set_session_cookie(
            response,
            request,
            access_token,
            max_age=max(
                0,
                claims["exp"]
                - int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
            ),
        )
        return "", True
    return access_token, False
