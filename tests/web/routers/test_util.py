"""
Integration tests for the util router endpoints.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_serve_custom_panorama_api_custom_exists(
    unauth_client: TestClient, tmp_path, app_context
):
    custom_pano = tmp_path / "panorama.jpeg"
    custom_pano.write_bytes(b"custom_image_data")

    with patch(
        "bedrock_server_manager.config.settings.Settings.config_dir",
        str(tmp_path),
        create=True,
    ):
        response = unauth_client.get("/api/panorama")
        assert response.status_code == 200


def test_serve_custom_panorama_api_default_fallback(
    unauth_client: TestClient, tmp_path, app_context
):
    # No custom pano
    default_pano = tmp_path / "image" / "panorama.jpeg"
    default_pano.parent.mkdir(parents=True, exist_ok=True)
    default_pano.write_bytes(b"default_image_data")

    with patch("bedrock_server_manager.web.routers.util.STATIC_DIR", str(tmp_path)):
        response = unauth_client.get("/api/panorama")
        assert response.status_code == 200


def test_serve_custom_panorama_api_not_found(unauth_client: TestClient, tmp_path):
    with patch("bedrock_server_manager.web.routers.util.STATIC_DIR", str(tmp_path)):
        response = unauth_client.get("/api/panorama")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


def test_serve_custom_panorama_api_exception(unauth_client: TestClient):
    with patch("bedrock_server_manager.web.routers.util.os.path.isfile") as mock_isfile:
        mock_isfile.side_effect = Exception("File system error")
        response = unauth_client.get("/api/panorama")
        assert response.status_code == 500
        assert "error serving" in response.json()["detail"].lower()


def test_get_root_favicon_success(unauth_client: TestClient, tmp_path):
    favicon = tmp_path / "image" / "icon" / "favicon.ico"
    favicon.parent.mkdir(parents=True, exist_ok=True)
    favicon.write_bytes(b"favicon_data")

    with patch("bedrock_server_manager.web.routers.util.STATIC_DIR", str(tmp_path)):
        response = unauth_client.get("/favicon.ico")
        assert response.status_code == 200


def test_get_root_favicon_not_found(unauth_client: TestClient, tmp_path):
    with patch("bedrock_server_manager.web.routers.util.STATIC_DIR", str(tmp_path)):
        response = unauth_client.get("/favicon.ico")
        assert response.status_code == 404


def test_serve_webmanifest_success(unauth_client: TestClient, tmp_path):
    manifest = tmp_path / "site.webmanifest"
    manifest.write_bytes(b"manifest_data")

    with patch("bedrock_server_manager.web.routers.util.STATIC_DIR", str(tmp_path)):
        response = unauth_client.get("/site.webmanifest")
        assert response.status_code == 200


def test_serve_webmanifest_not_found(unauth_client: TestClient, tmp_path):
    with patch("bedrock_server_manager.web.routers.util.STATIC_DIR", str(tmp_path)):
        response = unauth_client.get("/site.webmanifest")
        assert response.status_code == 404
