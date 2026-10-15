"""Apply one session-cookie policy to setup, login, refresh, and logout."""

from urllib.parse import quote

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
