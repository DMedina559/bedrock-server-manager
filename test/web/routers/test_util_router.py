import tempfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi.responses import FileResponse
from fastapi.testclient import TestClient


import os


def test_serve_custom_panorama_api_custom(authenticated_client, app_context):
    """Test the serve_custom_panorama_api route with a custom panorama."""
    panorama_file = os.path.join(app_context.settings.config_dir, "panorama.jpeg")
    with open(panorama_file, "w") as f:
        f.write("fake image data")

    response = authenticated_client.get("/api/panorama")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.text == "fake image data"


@patch("bedrock_server_manager.web.routers.util.os.path.isfile")
def test_serve_custom_panorama_api_default(
    mock_isfile, authenticated_client, app_context
):
    """Test the serve_custom_panorama_api route with a default panorama."""
    with tempfile.NamedTemporaryFile(suffix=".jpeg") as tmp:
        app_context.config_dir = "/fake/path"
        mock_isfile.side_effect = [False, True]

        response = authenticated_client.get("/api/panorama")
        assert response.status_code == 200


@patch("bedrock_server_manager.web.routers.util.os.path.isfile")
def test_serve_custom_panorama_api_not_found(
    mock_isfile, authenticated_client, app_context
):
    """Test the serve_custom_panorama_api route with no panorama found."""
    app_context.config_dir = "/fake/path"
    mock_isfile.return_value = False

    response = authenticated_client.get("/api/panorama")
    assert response.status_code == 404


def test_serve_world_icon_api_custom(authenticated_client, real_bedrock_server):
    """Test the serve_world_icon_api route with a custom icon."""
    world_name = real_bedrock_server.get_world_name()
    world_dir = os.path.join(real_bedrock_server.server_dir, "worlds", world_name)
    os.makedirs(world_dir, exist_ok=True)
    icon_path = os.path.join(world_dir, "world_icon.jpeg")
    with open(icon_path, "w") as f:
        f.write("fake icon data")

    response = authenticated_client.get(
        f"/api/server/{real_bedrock_server.server_name}/world/icon"
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.text == "fake icon data"


@patch("bedrock_server_manager.web.routers.util.os.path.isfile")
def test_serve_world_icon_api_default(
    mock_isfile, authenticated_client, app_context, tmp_path, mocker
):
    """Test the serve_world_icon_api route with a default icon."""
    # Setup mock server to fallback to default
    mock_server = MagicMock()
    mock_server.has_world_icon.return_value = False
    mocker.patch.object(app_context, "get_server", return_value=mock_server)
    mocker.patch("bedrock_server_manager.web.routers.util.STATIC_DIR", str(tmp_path))

    # Create the fake default icon file
    default_icon_dir = tmp_path / "image" / "icon"
    default_icon_dir.mkdir(parents=True)
    (default_icon_dir / "favicon.ico").write_text("fake default icon")

    # Mock isfile to check for custom then default
    mock_isfile.return_value = True

    # Make the request
    response = authenticated_client.get("/api/server/test-server/world/icon")

    # Assert the response
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/vnd.microsoft.icon"
    assert response.text == "fake default icon"


@patch("bedrock_server_manager.web.routers.util.os.path.isfile")
def test_serve_world_icon_api_not_found(
    mock_isfile, authenticated_client, app_context, mocker
):
    """Test the serve_world_icon_api route with no icon found."""
    mock_server = MagicMock()
    mock_server.world_icon_filesystem_path = "/fake/path"
    mock_server.has_world_icon.return_value = False
    mocker.patch.object(app_context, "get_server", return_value=mock_server)
    mock_isfile.return_value = False

    response = authenticated_client.get("/api/server/test-server/world/icon")
    assert response.status_code == 404


@patch("bedrock_server_manager.web.routers.util.os.path.exists")
def test_get_root_favicon_not_found(mock_exists, client: TestClient):
    """Test the get_root_favicon route with no favicon found."""
    mock_exists.return_value = False

    response = client.get("/favicon.ico", follow_redirects=False)
    assert response.status_code == 404


def test_catch_all_api_route_authenticated(authenticated_client: TestClient):
    """Test the catch_all_api_route with an authenticated user."""
    response = authenticated_client.get("/invalid/path")
    assert response.status_code == 200
    assert "Bedrock Server Manager" in response.text


def test_catch_all_api_route_unauthenticated(client: TestClient, authenticated_user):
    """Test the catch_all_api_route with an unauthenticated user."""
    response = client.get("/invalid/path", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/auth/login"
