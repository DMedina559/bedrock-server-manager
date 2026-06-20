import os
import tempfile
from unittest.mock import patch

from fastapi.testclient import TestClient


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
    with tempfile.NamedTemporaryFile(suffix=".jpeg"):
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


@patch("bedrock_server_manager.web.routers.util.os.path.exists")
def test_get_root_favicon_not_found(mock_exists, client: TestClient):
    """Test the get_root_favicon route with no favicon found."""
    mock_exists.return_value = False

    response = client.get("/favicon.ico", follow_redirects=False)
    assert response.status_code == 404
