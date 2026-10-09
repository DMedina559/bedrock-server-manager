async def test_configuration_paths(real_bedrock_server):
    """Read and write settings and custom values through typed configuration."""
    server = real_bedrock_server

    # Since it uses the DB in the background, we can just use setters and getters
    await server.configuration.update("server_info.status", "STOPPED")
    await server.configuration.update("custom.test_key", "test_value")

    assert server.configuration.read("server_info.status") == "STOPPED"
    assert server.configuration.read("custom.test_key") == "test_value"

    await server.configuration.update("custom.test_key", "new_value")
    assert server.configuration.read("custom.test_key") == "new_value"

    # Check boolean values correctly read
    await server.configuration.update("custom.bool_val", True)
    assert server.configuration.read("custom.bool_val") is True


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
        server.configuration.update("server_info.installed_version", "new")
    )
    await entered.wait()
    await server.configuration.update("settings.autostart", True)
    release.set()
    await initial
    record = server.state.servers.get(server.server_name)
    assert record.installed_version == "new"
    assert record.autostart


async def test_invalid_nested_write_is_atomic(real_bedrock_server):
    import pytest
    from pydantic import ValidationError

    server = real_bedrock_server
    await server.configuration.update("custom.valid", 1)
    before = server.state.servers.get(server.server_name)
    with pytest.raises(ValidationError):
        await server.configuration.update("custom.invalid", float("nan"))
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
    server.process._publish_running(False)
    assert server.players == []
    assert server.player_count == 0


async def test_status_read_does_not_reconcile_persisted_state(real_bedrock_server):
    server = real_bedrock_server
    await server.configuration.update("server_info.status", "RUNNING")
    assert await server.get_status() == "STOPPED"
    assert server.configuration.snapshot().status == "RUNNING"
    await server.reconcile_status(False)
    assert server.configuration.snapshot().status == "STOPPED"


def test_configuration_reads_do_not_register_servers(app_context):
    server = app_context.get_server("not_installed")
    assert server.configuration.snapshot().installed_version == "UNKNOWN"
    assert app_context.state.servers.get(server.server_name) is None


async def test_configuration_write_requires_storage(app_context):
    import pytest

    from bedrock_server_manager.core.bedrock_server import BedrockServer
    from bedrock_server_manager.error import ConfigurationError

    server = BedrockServer(
        "standalone", settings=app_context.settings, state=app_context.state
    )
    with pytest.raises(ConfigurationError):
        await server.set_autostart(True)
