import json
import os
from unittest.mock import AsyncMock, MagicMock

import pytest


async def test_get_formatted_permissions(real_bedrock_server):
    """Test retrieving formatted permissions including names from a map."""
    server = real_bedrock_server
    permissions_path = server.permissions_json_path

    perm_data = [
        {"permission": "operator", "xuid": "12345"},
        {"permission": "member", "xuid": "67890"},
    ]

    with open(permissions_path, "w") as f:
        json.dump(perm_data, f)

    # Note: get_formatted_permissions internally queries known players from the db
    # We will simulate this by mocking get_known_players or inserting into db.
    # We can mock it here for test simplicity or just allow it to fall back to Unknown.
    # The current async version uses db_session_manager directly. Let's patch `get_known_players`

    # In order to not overcomplicate the database insertion here, let's just assert the default fallback behavior for the first,
    # or patch the get_known_players function.

    mock_known = [{"xuid": "12345", "name": "player1"}]
    # Fix patching for the import location

    import unittest.mock

    with unittest.mock.patch(
        "bedrock_server_manager.core.server.permissions_mixin.get_known_players",
        new_callable=AsyncMock,
    ) as mock_get_known_players:
        mock_get_known_players.return_value = mock_known
        mock_db_session_manager = (
            MagicMock()
        )  # We just need something to pass to the mocked function
        formatted = await server.get_formatted_permissions(mock_db_session_manager)

    assert len(formatted) == 2
    # Sort order: 'p' comes before 'u' (player1 vs Unknown)
    assert formatted[0]["xuid"] == "12345"
    assert formatted[0]["permission_level"] == "operator"
    assert formatted[0]["name"] == "player1"

    assert formatted[1]["xuid"] == "67890"
    assert formatted[1]["permission_level"] == "member"
    assert formatted[1]["name"] == "Unknown (XUID: 67890)"


async def test_set_player_permission_new_player(real_bedrock_server):
    """Test setting permission for a new player."""
    server = real_bedrock_server
    await server.set_player_permission("12345", "operator", "player1")

    permissions_path = server.permissions_json_path
    with open(permissions_path, "r") as f:
        data = json.load(f)
        assert len(data) == 1
        assert data[0] == {"permission": "operator", "xuid": "12345", "name": "player1"}


async def test_set_player_permission_update_existing(real_bedrock_server):
    """Test updating permission for an existing player."""
    server = real_bedrock_server
    permissions_path = server.permissions_json_path
    perm_data = [{"permission": "member", "xuid": "12345", "name": "existing"}]
    with open(permissions_path, "w") as f:
        json.dump(perm_data, f)

    await server.set_player_permission("12345", "operator")

    with open(permissions_path, "r") as f:
        data = json.load(f)
        assert len(data) == 1
        assert data[0]["permission"] == "operator"
        assert data[0]["xuid"] == "12345"


async def test_set_player_permission_visitor(real_bedrock_server):
    """Test setting permission to visitor updates them in the list."""
    server = real_bedrock_server
    permissions_path = server.permissions_json_path
    perm_data = [{"permission": "operator", "xuid": "12345"}]
    with open(permissions_path, "w") as f:
        json.dump(perm_data, f)

    await server.set_player_permission("12345", "visitor")

    with open(permissions_path, "r") as f:
        data = json.load(f)
        assert len(data) == 1
        assert data[0]["permission"] == "visitor"


async def test_set_player_permission_unwritable_file(real_bedrock_server):
    """Test setting permission fails gracefully if file is unwritable."""
    server = real_bedrock_server
    permissions_path = server.permissions_json_path
    with open(permissions_path, "w") as f:
        f.write("[]")

    os.chmod(permissions_path, 0o444)
    os.chmod(os.path.dirname(permissions_path), 0o555)
    try:
        with pytest.raises(Exception):
            await server.set_player_permission("12345", "operator")
    finally:
        os.chmod(os.path.dirname(permissions_path), 0o755)
        os.chmod(permissions_path, 0o644)
