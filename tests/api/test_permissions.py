from unittest.mock import MagicMock

import pytest

from bedrock_server_manager.api.permissions import get_permissions, set_permissions
from bedrock_server_manager.error import BSMError, InvalidServerNameError


def test_set_permissions_success(app_context, monkeypatch):
    """Test set_permissions maps directly to the server core effectively."""
    mock_server = MagicMock()
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = set_permissions("test_server", "xuid1", "p1", "operator", app_context)

    assert result["status"] == "success"
    assert "set to 'operator'" in result["message"]


def test_set_permissions_invalid_server(app_context):
    """Test set_permissions raises on bad server names."""
    with pytest.raises(InvalidServerNameError):
        set_permissions("", "xuid1", "p1", "operator", app_context)


def test_set_permissions_error(app_context, monkeypatch):
    """Test set_permissions catches specific permission assignment failures."""
    mock_server = MagicMock()
    mock_server.set_player_permission.side_effect = BSMError("Access denied")
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = set_permissions("test_server", "xuid1", "p1", "operator", app_context)

    assert result["status"] == "error"
    assert "Failed to configure permission" in result["message"]


def test_get_permissions_success(app_context, monkeypatch):
    """Test get_permissions aggregates known players from the system appropriately."""
    mock_server = MagicMock()
    mock_server.get_formatted_permissions.return_value = [
        {"xuid": "xuid1", "name": "p1", "permission_level": "operator"}
    ]
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    # Mock player API
    monkeypatch.setattr(
        "bedrock_server_manager.api.permissions.player_api.get_all_known_players_api",
        MagicMock(
            return_value={
                "status": "success",
                "players": [{"xuid": "xuid2", "name": "p2"}],
            }
        ),
    )

    result = get_permissions("test_server", app_context)

    assert result["status"] == "success"
    assert (
        len(result["permissions"]) == 2
    )  # One from formatted, one appended from known players
    assert result["permissions"][0]["name"] == "p1"
    assert result["permissions"][1]["name"] == "p2"


def test_get_permissions_missing_name(app_context):
    """Test get_permissions explicitly handles empty paths safely."""
    result = get_permissions("", app_context)
    assert result["status"] == "error"
    assert "cannot be empty" in result["message"]


def test_get_permissions_error(app_context, monkeypatch):
    """Test get_permissions relays core extraction issues accurately."""
    mock_server = MagicMock()
    mock_server.get_formatted_permissions.side_effect = BSMError("Config busted")
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    monkeypatch.setattr(
        "bedrock_server_manager.api.permissions.player_api.get_all_known_players_api",
        MagicMock(return_value={"status": "success"}),
    )

    result = get_permissions("test_server", app_context)

    assert result["status"] == "error"
    assert "Config busted" in result["message"]
