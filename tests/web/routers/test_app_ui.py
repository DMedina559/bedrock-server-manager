from unittest.mock import patch

from fastapi.responses import Response


def test_redirect_v2_root(client):
    """Test that /v2 redirects to /app/"""
    response = client.get("/v2", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/app/"


def test_redirect_v2_path(client):
    """Test that /v2/some/path redirects to /app/some/path"""
    response = client.get("/v2/some/path", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/app/some/path"


def test_redirect_app_root(client):
    """Test that /app redirects to /app/"""
    response = client.get("/app", follow_redirects=False)
    # The middleware in vite.config.js handles this in dev, but in prod/app.py?
    # app.py doesn't have a middleware for /app -> /app/ redirect.
    # BUT app_ui.py has:
    # @router.get("/app", include_in_schema=False)
    # async def redirect_app_root():
    #    return RedirectResponse(url="/app/")
    assert response.status_code == 307
    assert response.headers["location"] == "/app/"


@patch("bedrock_server_manager.web.routers.app_ui.os.path.exists")
@patch("bedrock_server_manager.web.routers.app_ui.FileResponse")
def test_serve_spa_success(mock_file_response, mock_exists, client):
    """Test serving the SPA index.html when it exists."""
    mock_exists.return_value = True
    # We return a simple Response object to simulate FileResponse behavior for the test client
    mock_file_response.return_value = Response(content="SPA Content")

    response = client.get("/app/dashboard")
    assert response.status_code == 200
    assert response.text == "SPA Content"

    # Verify checking for assets
    mock_exists.assert_called_once()
    args, _ = mock_exists.call_args
    assert "index.html" in args[0]


@patch("bedrock_server_manager.web.routers.app_ui.os.path.exists")
def test_serve_spa_missing(mock_exists, client):
    """Test serving the SPA when index.html is missing."""
    mock_exists.return_value = False

    response = client.get("/app/dashboard")
    assert (
        response.status_code == 200
    )  # It returns a JSON message, which is 200 OK by default
    assert response.json() == {"message": "App UI not built or installed."}


def test_serve_spa_assets_404(client):
    """Test that /app/assets/... returns 404 from the router (if static mount misses it or for specific logic)"""
    # The router explicitly checks for assets/ and returns 404
    response = client.get("/app/assets/something.js")
    assert (
        response.status_code == 404
    ), f"Expected 404, got {response.status_code}. Body: {response.text}"
    assert response.json() == {"detail": "Asset not found"}
