import pytest

from bedrock_server_manager.error import UserInputError


async def test_manage_json_config(real_bedrock_server):
    """Test getting, setting, and checking values via _manage_json_config."""
    server = real_bedrock_server

    # Since it uses the DB in the background, we can just use setters and getters
    await server._manage_json_config(
        key="server_info.status", operation="write", value="STOPPED"
    )
    await server._manage_json_config(
        key="custom.test_key", operation="write", value="test_value"
    )

    assert (
        await server._manage_json_config(key="server_info.status", operation="read")
        == "STOPPED"
    )
    assert (
        await server._manage_json_config(key="custom.test_key", operation="read")
        == "test_value"
    )

    await server._manage_json_config(
        key="custom.test_key", operation="write", value="new_value"
    )
    assert (
        await server._manage_json_config(key="custom.test_key", operation="read")
        == "new_value"
    )

    # Check boolean values correctly read
    await server._manage_json_config(
        key="custom.bool_val", operation="write", value=True
    )
    assert (
        await server._manage_json_config(key="custom.bool_val", operation="read")
        is True
    )

    # Check invalid action
    with pytest.raises(UserInputError):
        await server._manage_json_config(key="key", operation="invalid_action")


async def test_get_set_version(real_bedrock_server):
    """Test standard getters and setters for version."""
    server = real_bedrock_server
    await server.set_version("1.20.10.01")
    assert await server.get_version() == "1.20.10.01"


async def test_get_set_status_in_config(real_bedrock_server):
    """Test standard getters and setters for status."""
    server = real_bedrock_server
    await server.set_status_in_config("RUNNING")
    assert await server.get_status_from_config() == "RUNNING"


async def test_get_set_autoupdate(real_bedrock_server):
    """Test autoupdate property methods."""
    server = real_bedrock_server
    await server.set_autoupdate(True)
    assert await server.get_autoupdate() is True


async def test_get_set_autostart(real_bedrock_server):
    """Test autostart property methods."""
    server = real_bedrock_server
    await server.set_autostart(True)
    assert await server.get_autostart() is True


async def test_get_set_target_version(real_bedrock_server):
    """Test target version property methods."""
    server = real_bedrock_server
    await server.set_target_version("latest")
    assert await server.get_target_version() == "latest"


async def test_concurrent_initial_writes_preserve_both_values(
    real_bedrock_server, monkeypatch
):
    import asyncio

    server = real_bedrock_server
    server.state.servers.remove(server.server_name)
    entered = asyncio.Event()
    release = asyncio.Event()
    original = server.storage.apply_changeset
    first = True

    async def delayed(state, changeset):
        nonlocal first
        if first:
            first = False
            entered.set()
            await release.wait()
        await original(state, changeset)

    monkeypatch.setattr(server.storage, "apply_changeset", delayed)
    initial = asyncio.create_task(
        server._manage_json_config("server_info.installed_version", "write", "new")
    )
    await entered.wait()
    await server._manage_json_config("settings.autostart", "write", True)
    release.set()
    await initial
    record = server.state.servers.get(server.server_name)
    assert record.installed_version == "new"
    assert record.autostart


async def test_invalid_nested_write_is_atomic(real_bedrock_server):
    import pytest
    from pydantic import ValidationError

    server = real_bedrock_server
    await server._manage_json_config("custom.valid", "write", 1)
    before = server.state.servers.get(server.server_name)
    with pytest.raises(ValidationError):
        await server._manage_json_config("custom.invalid", "write", float("nan"))
    assert server.state.servers.get(server.server_name) == before


async def test_core_players_share_runtime_and_return_snapshots(real_bedrock_server):
    server = real_bedrock_server
    server.players = [{"name": "Player", "xuid": "1"}]
    assert server.player_count == 1
    snapshot = server.state.runtime.get_server_runtime(server.server_name)
    assert snapshot.players[0].name == "Player"
    server.players[0]["name"] = "Changed"
    assert (
        server.state.runtime.get_server_runtime(server.server_name).players[0].name
        == "Player"
    )
    server._publish_running(False)
    assert server.players == []
    assert server.player_count == 0
