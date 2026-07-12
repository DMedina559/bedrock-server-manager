from unittest.mock import MagicMock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from bedrock_server_manager.web.deps.server import validate_server_exists


@pytest.fixture
def server_test_app(app_context):
    app = FastAPI()
    app.state.app_context = app_context

    @app.get("/test-server/{server_name}")
    async def get_server_route(server_name: str = Depends(validate_server_exists)):
        return {"server": server_name}

    return app


def test_validate_server_exists_success(server_test_app, monkeypatch):
    """Test validate_server_exists with a valid existing server."""
    monkeypatch.setattr(
        "bedrock_server_manager.utils.server.validate_server",
        MagicMock(return_value=True),
    )
    monkeypatch.setattr(
        "bedrock_server_manager.utils.server.core_validate_server_name_format",
        MagicMock(),
    )

    client = TestClient(server_test_app)
    response = client.get("/test-server/valid_server")
    assert response.status_code == 200
    assert response.json()["server"] == "valid_server"


def test_validate_server_exists_not_found(server_test_app, monkeypatch):
    """Test validate_server_exists with a non-existent server raises 404."""
    monkeypatch.setattr(
        "bedrock_server_manager.utils.server.validate_server",
        MagicMock(return_value=False),
    )
    monkeypatch.setattr(
        "bedrock_server_manager.utils.server.core_validate_server_name_format",
        MagicMock(),
    )

    client = TestClient(server_test_app)
    response = client.get("/test-server/missing_server")
    assert response.status_code == 404
    assert "not installed or the installation is invalid" in response.json()["detail"]


def test_validate_server_exists_invalid_name(server_test_app, monkeypatch):
    """Test validate_server_exists with an invalid server name raises 400."""
    from bedrock_server_manager.error import InvalidServerNameError

    def mock_invalid_format(*args, **kwargs):
        raise InvalidServerNameError("Invalid format")

    monkeypatch.setattr(
        "bedrock_server_manager.utils.server.core_validate_server_name_format",
        mock_invalid_format,
    )

    client = TestClient(server_test_app)
    response = client.get("/test-server/invalid@name!")
    assert response.status_code == 400
    assert "Invalid format" in response.json()["detail"]
