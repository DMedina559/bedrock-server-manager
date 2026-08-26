from fastapi import Request
from fastapi.responses import RedirectResponse


async def setup_check_middleware(request: Request, call_next):
    """
    Middleware that checks if the application needs setup and redirects users
    to the setup page if so. It bypasses this check for API routes and specific
    allowed paths (like static assets or the setup SPA itself).
    """
    # Paths that should be accessible even if setup is not complete
    allowed_paths = [
        "/setup/status",  # API status check
        "/setup/create-first-user",  # API create user
        "/app",  # The SPA itself
        "/themes",
        "/favicon.ico",
        "/site.webmanifest",
        "/auth/token",
        "/docs",
        "/openapi.json",
    ]

    req_path = request.scope.get("path", "")
    root_path = request.scope.get("root_path", "")
    if root_path and req_path.startswith(root_path):
        req_path = req_path[len(root_path) :]  # noqa: E203
        if not req_path:
            req_path = "/"

    # Allow static assets to pass through
    if (
        req_path.startswith("/app/assets")
        or req_path.startswith("/app/image")
        or req_path.startswith("/image")
    ):
        response = await call_next(request)
        return response

    if request.app.state.app_context.needs_setup and not any(
        req_path.startswith(p) for p in allowed_paths
    ):

        if req_path.startswith("/api"):
            pass
        elif not req_path.startswith("/app"):
            app_url = request.url_for("serve_spa")
            return RedirectResponse(url=str(app_url))

    response = await call_next(request)
    return response
