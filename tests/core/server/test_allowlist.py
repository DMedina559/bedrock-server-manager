import json
import os
from pathlib import Path

import pytest

from bedrock_server_manager.error import ConfigParseError, FileOperationError


async def test_get_allowlist_scenarios(real_bedrock_server):
    """Test retrieving allowlist from missing, empty, valid, and malformed files."""
    server = real_bedrock_server
    allowlist_path = Path(server.paths.allowlist_json_path)

    if allowlist_path.exists():
        allowlist_path.unlink()
    assert await server.allowlist.get_allowlist() == []

    allowlist_path.write_text("", encoding="utf-8")
    assert await server.allowlist.get_allowlist() == []

    allowlist_data = [{"name": "player1", "xuid": "12345", "ignoresPlayerLimit": False}]
    allowlist_path.write_text(json.dumps(allowlist_data), encoding="utf-8")
    assert await server.allowlist.get_allowlist() == allowlist_data

    allowlist_path.write_text("{invalid_json}", encoding="utf-8")
    with pytest.raises(ConfigParseError, match="Invalid JSON in allowlist"):
        await server.allowlist.get_allowlist()

    allowlist_path.write_text(json.dumps({"key": "value"}), encoding="utf-8")
    with pytest.raises(ConfigParseError):
        await server.allowlist.get_allowlist()


async def test_add_and_remove_allowlist_scenarios(real_bedrock_server):
    """Test adding, deduplicating, validating, and removing allowlist players."""
    server = real_bedrock_server
    allowlist_path = Path(server.paths.allowlist_json_path)
    if allowlist_path.exists():
        allowlist_path.unlink()

    assert await server.allowlist.remove_from_allowlist("player1") is False

    await server.allowlist.add_to_allowlist(["invalid_entry"])  # type: ignore
    await server.allowlist.add_to_allowlist([{"xuid": "12345"}])
    assert await server.allowlist.get_allowlist() == []

    await server.allowlist.add_to_allowlist([{"name": "player1", "xuid": "12345"}])
    assert json.loads(allowlist_path.read_text(encoding="utf-8")) == [
        {"name": "player1", "xuid": "12345", "ignoresPlayerLimit": False}
    ]
    assert (
        await server.allowlist.add_to_allowlist([{"name": "player1", "xuid": "12345"}])
        == 0
    )

    added = await server.allowlist.add_to_allowlist(
        [
            {"name": "player2", "xuid": "67890"},
            {"name": "player3", "xuid": "54321"},
            {"name": "player2", "xuid": "09876"},
        ]
    )
    allowlist = await server.allowlist.get_allowlist()
    assert added == 2
    assert {p["name"] for p in allowlist} == {"player1", "player2", "player3"}

    assert await server.allowlist.remove_from_allowlist("non_existent_player") is False
    assert await server.allowlist.remove_from_allowlist("player1") is True
    assert {p["name"] for p in await server.allowlist.get_allowlist()} == {
        "player2",
        "player3",
    }


async def test_allowlist_unwritable_file_and_malformed_preservation(
    real_bedrock_server,
):
    """Test read-only failures and preserving malformed allowlist files."""
    server = real_bedrock_server
    allowlist_path = server.paths.allowlist_json_path
    await server.allowlist.add_to_allowlist([{"name": "player1", "xuid": "12345"}])

    os.chmod(allowlist_path, 0o444)
    os.chmod(os.path.dirname(allowlist_path), 0o555)
    try:
        with pytest.raises(FileOperationError, match="Failed to write allowlist"):
            await server.allowlist.add_to_allowlist(
                [{"name": "player2", "xuid": "67890"}]
            )
        with pytest.raises(FileOperationError, match="Failed to write allowlist"):
            await server.allowlist.remove_from_allowlist("player1")
    finally:
        os.chmod(os.path.dirname(allowlist_path), 0o755)
        os.chmod(allowlist_path, 0o644)

    path = Path(allowlist_path)
    for content in ("{}", "null", "false", "{broken", '[{"unexpected": "value"}]'):
        path.write_text(content, encoding="utf-8")
        before = path.read_bytes()
        with pytest.raises(ConfigParseError):
            await server.allowlist.add_to_allowlist([{"name": "Alex"}])
        assert path.read_bytes() == before
