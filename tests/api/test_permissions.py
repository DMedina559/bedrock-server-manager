from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.models import (
    GetAllKnownPlayersResponse,
    GetPermissionsRequest,
    SetPermissionsRequest,
)
from bedrock_server_manager.api.permissions import get_permissions, set_permissions
from bedrock_server_manager.error import BSMError


async def test_set_permissions_success(app_context, monkeypatch):
    """Test set_permissions maps directly to the server core effectively."""
    mock_server = MagicMock()
    mock_server.set_player_permission = AsyncMock()
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = (
        await set_permissions(
            request=SetPermissionsRequest(
                server_name="test_server",
                xuid="xuid1",
                player_name="p1",
                permission="operator",
            ),
            app_context=app_context,
        )
    ).model_dump(mode="python")

    assert result["status"] == "success"
    assert "set to 'operator'" in result["message"]


async def test_set_permissions_invalid_server(app_context):
    """Test set_permissions raises on bad server names."""
    with pytest.raises(ValidationError):
        (
            await set_permissions(
                request=SetPermissionsRequest(
                    server_name="",
                    xuid="xuid1",
                    player_name="p1",
                    permission="operator",
                ),
                app_context=app_context,
            )
        ).model_dump(mode="python")


async def test_set_permissions_error(app_context, monkeypatch):
    """Test set_permissions catches specific permission assignment failures."""
    mock_server = MagicMock()
    mock_server.set_player_permission = AsyncMock(side_effect=BSMError("Access denied"))
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    with pytest.raises(BSMError):
        (
            await set_permissions(
                request=SetPermissionsRequest(
                    server_name="test_server",
                    xuid="xuid1",
                    player_name="p1",
                    permission="operator",
                ),
                app_context=app_context,
            )
        ).model_dump(mode="python")


async def test_get_permissions_success(app_context, monkeypatch):
    """Test get_permissions aggregates known players from the system appropriately."""
    mock_server = MagicMock()
    mock_server.get_formatted_permissions = AsyncMock(
        return_value=[{"xuid": "xuid1", "name": "p1", "permission_level": "operator"}]
    )
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    # Mock player API
    monkeypatch.setattr(
        "bedrock_server_manager.api.permissions.player_api.get_all_known_players",
        AsyncMock(
            return_value=GetAllKnownPlayersResponse(
                players=[{"xuid": "xuid2", "name": "p2"}]
            )
        ),
    )

    result = (
        await get_permissions(
            request=GetPermissionsRequest(server_name="test_server"),
            app_context=app_context,
        )
    ).model_dump(mode="python")

    assert result["status"] == "success"
    assert (
        len(result["permissions"]) == 2
    )  # One from formatted, one appended from known players
    assert result["permissions"][0]["name"] == "p1"
    assert result["permissions"][1]["name"] == "p2"


async def test_get_permissions_missing_name(app_context):
    """Test get_permissions explicitly handles empty paths safely."""
    with pytest.raises(ValidationError):
        (
            await get_permissions(
                request=GetPermissionsRequest(server_name=""), app_context=app_context
            )
        ).model_dump(mode="python")


async def test_get_permissions_error(app_context, monkeypatch):
    """Test get_permissions relays core extraction issues accurately."""
    mock_server = MagicMock()
    mock_server.get_formatted_permissions = AsyncMock(
        side_effect=BSMError("Config busted")
    )
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    monkeypatch.setattr(
        "bedrock_server_manager.api.permissions.player_api.get_all_known_players",
        AsyncMock(return_value=GetAllKnownPlayersResponse(players=[])),
    )

    with pytest.raises(BSMError):
        (
            await get_permissions(
                request=GetPermissionsRequest(server_name="test_server"),
                app_context=app_context,
            )
        ).model_dump(mode="python")
