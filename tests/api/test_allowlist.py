from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.allowlist import (
    add_to_allowlist,
    get_allowlist,
    remove_from_allowlist,
)
from bedrock_server_manager.api.models import (
    AddToAllowlistRequest,
    GetAllowlistRequest,
    RemoveFromAllowlistRequest,
)
from bedrock_server_manager.error import BSMError


async def test_add_to_allowlist_success(app_context, monkeypatch):
    """Test add_to_allowlist parses valid lists correctly."""
    mock_server = MagicMock()
    mock_server.add_to_allowlist = AsyncMock(return_value=1)
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = (
        await add_to_allowlist(
            request=AddToAllowlistRequest(
                server_name="test_server",
                new_players_data=[{"name": "player1", "xuid": "123"}],
            ),
            app_context=app_context,
        )
    ).model_dump(mode="python")

    assert result["status"] == "success"
    assert result["added_count"] == 1


async def test_add_to_allowlist_empty_server(app_context):
    """Test add_to_allowlist throws on missing server strings."""
    with pytest.raises(ValidationError):
        (
            await add_to_allowlist(
                request=AddToAllowlistRequest(server_name="", new_players_data=[]),
                app_context=app_context,
            )
        ).model_dump(mode="python")


async def test_add_to_allowlist_invalid_list(app_context):
    """Test add_to_allowlist returns an error if players data is not a list."""
    with pytest.raises(ValidationError):
        (
            await add_to_allowlist(
                request=AddToAllowlistRequest(
                    server_name="test_server", new_players_data="not_a_list"
                ),
                app_context=app_context,
            )
        ).model_dump(mode="python")


async def test_get_allowlist_success(app_context, monkeypatch):
    """Test get_allowlist successfully retrieves from server."""
    mock_server = MagicMock()
    mock_server.get_allowlist = AsyncMock(return_value=[{"name": "p1"}])
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = (
        await get_allowlist(
            request=GetAllowlistRequest(server_name="test_server"),
            app_context=app_context,
        )
    ).model_dump(mode="python")

    assert result["status"] == "success"
    assert len(result["players"]) == 1


async def test_get_allowlist_missing_server(app_context):
    """Test get_allowlist throws error when no server string is provided."""
    with pytest.raises(ValidationError):
        (
            await get_allowlist(
                request=GetAllowlistRequest(server_name=""), app_context=app_context
            )
        ).model_dump(mode="python")


async def test_get_allowlist_bsmerror(app_context, monkeypatch):
    """Test get_allowlist wraps BSMError in error dict."""

    def raise_err(*args):
        raise BSMError("File broken")

    monkeypatch.setattr(app_context, "get_server", raise_err)

    with pytest.raises(BSMError):
        (
            await get_allowlist(
                request=GetAllowlistRequest(server_name="test_server"),
                app_context=app_context,
            )
        ).model_dump(mode="python")


async def test_remove_from_allowlist_success(app_context, monkeypatch):
    """Test remove_from_allowlist removes specific users and counts failures accurately."""
    mock_remove = AsyncMock(
        side_effect=[True, False]
    )  # First player exists, second doesnt
    mock_server = MagicMock()
    mock_server.remove_from_allowlist = mock_remove
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = (
        await remove_from_allowlist(
            request=RemoveFromAllowlistRequest(
                server_name="test_server", player_names=["p1", "p2"]
            ),
            app_context=app_context,
        )
    ).model_dump(mode="python")

    assert result["status"] == "success"
    assert "p1" in result["details"]["removed"]
    assert "p2" in result["details"]["not_found"]


async def test_remove_from_allowlist_empty(app_context):
    """Test remove_from_allowlist shortcuts immediately when list is empty."""
    result = (
        await remove_from_allowlist(
            request=RemoveFromAllowlistRequest(
                server_name="test_server", player_names=[]
            ),
            app_context=app_context,
        )
    ).model_dump(mode="python")

    assert result["status"] == "success"
    assert len(result["details"]["removed"]) == 0


async def test_remove_from_allowlist_missing_server(app_context):
    """Test remove_from_allowlist correctly validates server names."""
    with pytest.raises(ValidationError):
        (
            await remove_from_allowlist(
                request=RemoveFromAllowlistRequest(server_name="", player_names=["p1"]),
                app_context=app_context,
            )
        ).model_dump(mode="python")
