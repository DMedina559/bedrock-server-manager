from unittest.mock import MagicMock

from fastapi import Request
from fastapi.testclient import TestClient

from bedrock_server_manager.web.app import create_web_app


def test_create_web_app_initialization(app_context):
    """Test that create_web_app initializes and configures the FastAPI app correctly."""
    app = create_web_app(app_context)

    assert app.title == "Bedrock Server Manager"
    assert app.state.app_context == app_context
    assert app.openapi_url == "/api/openapi.json"

    # Check that some routers are mounted
    assert len(app.routes) > 0


def test_setup_check_middleware_redirect(app_context, monkeypatch):
    """Test that the setup_check_middleware redirects to /app when setup is needed."""
    monkeypatch.setattr(
        "bedrock_server_manager.config.bcm_config.needs_setup",
        MagicMock(return_value=True),
    )

    app = create_web_app(app_context)
    client = TestClient(app)

    # Access a non-API route that is not allowed during setup
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/app"


def test_setup_check_middleware_api_passthrough(app_context, monkeypatch):
    """Test that API requests during setup don't redirect (they either pass or get handled by the route)."""
    monkeypatch.setattr(
        "bedrock_server_manager.config.bcm_config.needs_setup",
        MagicMock(return_value=True),
    )

    app = create_web_app(app_context)
    client = TestClient(app)

    # Access an API route
    response = client.get("/api/users", follow_redirects=False)
    # Should not redirect. The route itself might return 401 because we aren't auth'd.
    assert response.status_code != 307


def test_setup_check_middleware_allowed_paths(app_context, monkeypatch):
    """Test that allowed paths pass through even when setup is needed."""
    monkeypatch.setattr(
        "bedrock_server_manager.config.bcm_config.needs_setup",
        MagicMock(return_value=True),
    )

    app = create_web_app(app_context)
    client = TestClient(app)

    response = client.get("/docs", follow_redirects=False)
    assert response.status_code == 200


def test_setup_check_middleware_static_assets(app_context, monkeypatch):
    """Test that static assets paths pass through even when setup is needed."""
    monkeypatch.setattr(
        "bedrock_server_manager.config.bcm_config.needs_setup",
        MagicMock(return_value=True),
    )

    app = create_web_app(app_context)
    client = TestClient(app)

    response = client.get("/app/assets/test.js", follow_redirects=False)
    assert response.status_code != 307


def test_add_user_to_request_middleware(app_context, auth_client, test_user):
    """Test that the user is injected into the request state."""
    app = create_web_app(app_context)

    # We will test the middleware specifically by hitting a dummy endpoint that reads request.state
    @app.get("/test-middleware-user")
    def get_user(request: Request):
        user = getattr(request.state, "current_user", None)
        if user:
            return {"username": user.username}
        return {"username": None}

    client = TestClient(app)
    client.cookies = auth_client.cookies  # steal the auth cookie

    response = client.get("/test-middleware-user", follow_redirects=False)
    assert response.status_code == 200
    assert response.json()["username"] == test_user.username


def test_cors_middleware_configuration(app_context, monkeypatch):
    """Test CORS wildcard configuration dynamically sets allow_origin_regex."""
    monkeypatch.setattr(
        "bedrock_server_manager.config.bcm_config.get_config_value",
        MagicMock(return_value=["*"]),
    )

    app = create_web_app(app_context)

    # Find the CORSMiddleware
    from starlette.middleware.cors import CORSMiddleware

    cors_mw = None
    for mw in app.user_middleware:
        if mw.cls == CORSMiddleware:
            cors_mw = mw
            break

    assert cors_mw is not None

    assert cors_mw.kwargs.get("allow_origin_regex") == ".*"
