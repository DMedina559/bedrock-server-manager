import tempfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi.responses import FileResponse
from fastapi.testclient import TestClient


@pytest.mark.skip(reason="FileResponse is causing issues")
@patch("bedrock_server_manager.web.routers.util.FileResponse")
@patch("bedrock_server_manager.web.routers.util.os.path.isfile")
def test_serve_custom_panorama_api_custom(
    mock_isfile, mock_file_response, authenticated_client, mock_get_settings_instance
):
    """Test the serve_custom_panorama_api route with a custom panorama."""
    mock_get_settings_instance.config_dir = "/fake/path"
    mock_isfile.return_value = True

    async def fake_file_response(*args, **kwargs):
        return MagicMock(status_code=200)

    mock_file_response.side_effect = fake_file_response

    response = authenticated_client.get("/api/panorama")
    assert response.status_code == 200


@patch("bedrock_server_manager.web.routers.util.os.path.isfile")
def test_serve_custom_panorama_api_default(
    mock_isfile, authenticated_client, mock_get_settings_instance
):
    """Test the serve_custom_panorama_api route with a default panorama."""
    with tempfile.NamedTemporaryFile(suffix=".jpeg") as tmp:
        mock_get_settings_instance.config_dir = "/fake/path"
        mock_isfile.side_effect = [False, True]

        response = authenticated_client.get("/api/panorama")
        assert response.status_code == 200


@patch("bedrock_server_manager.web.routers.util.os.path.isfile")
def test_serve_custom_panorama_api_not_found(
    mock_isfile, authenticated_client, mock_get_settings_instance
):
    """Test the serve_custom_panorama_api route with no panorama found."""
    mock_get_settings_instance.config_dir = "/fake/path"
    mock_isfile.return_value = False

    response = authenticated_client.get("/api/panorama")
    assert response.status_code == 404


@pytest.mark.skip(reason="FileResponse is causing issues")
@pytest.mark.skip(reason="FileResponse is causing issues")
def test_serve_world_icon_api_default(authenticated_client):
    """Test the serve_world_icon_api route with a custom icon."""
    mock_get_server.return_value.world_icon_filesystem_path = "/fake/path"
    mock_get_server.return_value.has_world_icon.return_value = True
    mock_isfile.return_value = True

    async def fake_file_response(*args, **kwargs):
        return MagicMock(status_code=200)

    mock_file_response.side_effect = fake_file_response

    response = authenticated_client.get("/api/server/test-server/world/icon")
    assert response.status_code == 200


@pytest.mark.skip(reason="FileResponse is causing issues")
def test_serve_world_icon_api_default(authenticated_client):
    """Test the serve_world_icon_api route with a default icon."""
    mock_get_server.return_value.world_icon_filesystem_path = "/fake/path"
    mock_get_server.return_value.has_world_icon.return_value = False
    mock_isfile.side_effect = [False, True]
    mock_file_response.return_value = MagicMock(spec=FileResponse, background=None)
    mock_file_response.return_value.status_code = 200

    response = authenticated_client.get("/api/server/test-server/world/icon")
    assert response.status_code == 200


@patch("bedrock_server_manager.web.routers.util.get_server_instance")
@patch("bedrock_server_manager.web.routers.util.os.path.isfile")
def test_serve_world_icon_api_not_found(
    mock_isfile, mock_get_server, authenticated_client
):
    """Test the serve_world_icon_api route with no icon found."""
    mock_get_server.return_value.world_icon_filesystem_path = "/fake/path"
    mock_get_server.return_value.has_world_icon.return_value = False
    mock_isfile.return_value = False

    response = authenticated_client.get("/api/server/test-server/world/icon")
    assert response.status_code == 404


@patch("bedrock_server_manager.web.routers.util.os.path.exists")
def test_get_root_favicon(mock_exists, client: TestClient):
    """Test the get_root_favicon route with a successful response."""
    mock_exists.return_value = True

    response = client.get("/favicon.ico")
    assert response.status_code == 200


@patch("bedrock_server_manager.web.routers.util.os.path.exists")
def test_get_root_favicon_not_found(mock_exists, client: TestClient):
    """Test the get_root_favicon route with no favicon found."""
    mock_exists.return_value = False

    response = client.get("/favicon.ico")
    assert response.status_code == 404


def test_catch_all_api_route_authenticated(authenticated_client: TestClient):
    """Test the catch_all_api_route with an authenticated user."""
    response = authenticated_client.get("/invalid/path")
    assert response.status_code == 200
    assert "Bedrock Server Manager" in response.text


def test_catch_all_api_route_unauthenticated(client: TestClient):
    """Test the catch_all_api_route with an unauthenticated user."""
    response = client.get("/invalid/path", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/auth/login"
