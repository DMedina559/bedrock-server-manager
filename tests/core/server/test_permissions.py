import json
import os
from pathlib import Path

import pytest

from bedrock_server_manager.error import ConfigParseError, FileOperationError


async def test_permissions_formatting_and_updates(real_bedrock_server, app_context):
    """Test retrieving formatted permissions and setting/updating player permissions."""
    server = real_bedrock_server
    permissions_path = server.paths.permissions_json_path

    # Set new player permission
    await server.permissions.set_player_permission("12345", "operator", "player1")
    with open(permissions_path, "r") as f:
        data = json.load(f)
        assert data == [{"permission": "operator", "xuid": "12345", "name": "player1"}]

    # Update existing player permission
    await server.permissions.set_player_permission("12345", "visitor")
    with open(permissions_path, "r") as f:
        data = json.load(f)
        assert len(data) == 1 and data[0]["permission"] == "visitor"

    # Formatted permissions with known and unknown players
    perm_data = [
        {"permission": "operator", "xuid": "12345"},
        {"permission": "member", "xuid": "67890"},
    ]
    with open(permissions_path, "w") as f:
        json.dump(perm_data, f)

    await app_context.storage.save_players([{"xuid": "12345", "name": "player1"}])
    formatted = await server.permissions.get_formatted_permissions(app_context.storage)
    assert len(formatted) == 2
    assert formatted[0] == {
        "xuid": "12345",
        "permission_level": "operator",
        "name": "player1",
    }
    assert formatted[1] == {
        "xuid": "67890",
        "permission_level": "member",
        "name": "Unknown (XUID: 67890)",
    }


async def test_permissions_unwritable_and_malformed_preservation(real_bedrock_server):
    """Test unwritable permissions file and malformed configuration preservation."""
    server = real_bedrock_server
    permissions_path = server.paths.permissions_json_path
    path = Path(permissions_path)

    for content in ("{}", "null", "false", "{broken", '[{"unexpected": "value"}]'):
        path.write_text(content, encoding="utf-8")
        before = path.read_bytes()
        with pytest.raises(ConfigParseError):
            await server.permissions.set_player_permission("123", "operator", "Alex")
        assert path.read_bytes() == before

    path.write_text("[]", encoding="utf-8")
    os.chmod(permissions_path, 0o444)
    os.chmod(os.path.dirname(permissions_path), 0o555)
    try:
        with pytest.raises(FileOperationError, match="Failed to write permissions"):
            await server.permissions.set_player_permission("12345", "operator")
    finally:
        os.chmod(os.path.dirname(permissions_path), 0o755)
        os.chmod(permissions_path, 0o644)
