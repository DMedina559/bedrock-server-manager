"""
Integration tests for the util router endpoints.
"""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def test_serve_custom_panorama_api_custom_exists(
    unauth_client: TestClient, tmp_path, app_context
):
    # Create an actual subfolder so we can mock config_dir securely
    config_dir = tmp_path / "test_config"
    config_dir.mkdir(parents=True, exist_ok=True)
    custom_pano = config_dir / "panorama.jpeg"
    custom_pano.write_bytes(b"custom_image_data")
    app_context.settings.config_dir = str(config_dir)

    with patch(
        "bedrock_server_manager.config.settings.Settings.config_dir",
        str(config_dir),
        create=True,
    ):
        with patch("aiofiles.ospath.isfile", new_callable=AsyncMock) as mock_isfile:
            mock_isfile.side_effect = lambda x: (
                True if str(x) == str(custom_pano) else False
            )

            with patch(
                "os.path.isfile",
                side_effect=lambda x: True if str(x) == str(custom_pano) else False,
            ):
                response = unauth_client.get("/api/panorama")
                assert response.status_code == 200


def test_serve_custom_panorama_api_default_fallback(
    unauth_client: TestClient, tmp_path, app_context
):
    # Create an actual subfolder so we can mock config_dir securely
    config_dir = tmp_path / "test_config"
    config_dir.mkdir(parents=True, exist_ok=True)

    # No custom pano
    default_pano = tmp_path / "image" / "panorama.jpeg"
    default_pano.parent.mkdir(parents=True, exist_ok=True)
    default_pano.write_bytes(b"default_image_data")

    with patch(
        "bedrock_server_manager.config.settings.Settings.config_dir",
        str(config_dir),
        create=True,
    ):
        with patch("bedrock_server_manager.web.routers.util.STATIC_DIR", str(tmp_path)):
            with patch("aiofiles.ospath.isfile", new_callable=AsyncMock) as mock_isfile:
                mock_isfile.side_effect = lambda x: (
                    True if str(x) == str(default_pano) else False
                )

                with patch(
                    "os.path.isfile",
                    side_effect=lambda x: (
                        True if str(x) == str(default_pano) else False
                    ),
                ):
                    response = unauth_client.get("/api/panorama")
                    assert response.status_code == 200


def test_serve_custom_panorama_api_not_found(unauth_client: TestClient, tmp_path):
    with patch("bedrock_server_manager.web.routers.util.STATIC_DIR", str(tmp_path)):
        with patch("aiofiles.ospath.isfile", new_callable=AsyncMock) as mock_isfile:
            mock_isfile.return_value = False
            response = unauth_client.get("/api/panorama")
            assert response.status_code == 404
            assert "not found" in response.json()["error"]["message"].lower()


def test_serve_custom_panorama_api_exception(unauth_client: TestClient):
    with patch("aiofiles.ospath.isfile", new_callable=AsyncMock) as mock_isfile:
        mock_isfile.side_effect = Exception("File system error")
        response = unauth_client.get("/api/panorama")
        assert response.status_code == 500
        assert response.json()["error"]["message"] == "An unexpected error occurred."
