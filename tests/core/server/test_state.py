import asyncio

import pytest
from pydantic import ValidationError

from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.error import ConfigurationError


async def test_configuration_paths_and_getters_setters(real_bedrock_server):
    """Read and write settings, custom values, getters/setters, and runtime player snapshots."""
    server = real_bedrock_server

    await server.configuration.update("server_info.status", "STOPPED")
    await server.configuration.update("custom.test_key", "test_value")
    assert server.configuration.read("server_info.status") == "STOPPED"
    assert server.configuration.read("custom.test_key") == "test_value"

    await server.configuration.update("custom.test_key", "new_value")
    assert server.configuration.read("custom.test_key") == "new_value"

    await server.configuration.update("custom.bool_val", True)
    assert server.configuration.read("custom.bool_val") is True

    await server.set_version("1.20.10.01")
    assert await server.get_version() == "1.20.10.01"

    await server.set_status_in_config("RUNNING")
    assert await server.get_status_from_config() == "RUNNING"

    await server.set_autoupdate(True)
    assert await server.get_autoupdate() is True

    await server.set_autostart(True)
    assert await server.get_autostart() is True

    await server.set_target_version("latest")
    assert await server.get_target_version() == "latest"

    # Invalid nested write is atomic
    await server.configuration.update("custom.valid", 1)
    before = server.state.servers.get(server.server_name)
    with pytest.raises(ValidationError):
        await server.configuration.update("custom.invalid", float("nan"))
    assert server.state.servers.get(server.server_name) == before

    # Status read does not reconcile persisted state
    await server.configuration.update("server_info.status", "RUNNING")
    assert await server.get_status() == "STOPPED"
    assert server.configuration.snapshot().status == "RUNNING"
    # Normal process probes still reconcile the persisted status.
    assert not await server.is_running()
    assert server.configuration.snapshot().status == "STOPPED"
    await server.configuration.update("server_info.status", "RUNNING")
    await server.reconcile_status(False)
    assert server.configuration.snapshot().status == "STOPPED"

    # Core players share runtime and return snapshots
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


async def test_concurrent_initial_writes_preserve_both_values(
    real_bedrock_server, monkeypatch
):
    server = real_bedrock_server
    server.state.servers.remove(server.server_name)
    entered = asyncio.Event()
    release = asyncio.Event()
    original = server.storage.commit_record
    first = True

    async def delayed(state, changeset, name, **kwargs):
        nonlocal first
        if first:
            first = False
            entered.set()
            await release.wait()
        await original(state, changeset, name, **kwargs)

    monkeypatch.setattr(server.storage, "commit_record", delayed)
    initial = asyncio.create_task(
        server.configuration.update("server_info.installed_version", "new")
    )
    async with asyncio.timeout(10):
        await entered.wait()
    await server.configuration.update("settings.autostart", True)
    release.set()
    await initial
    record = server.state.servers.get(server.server_name)
    assert record.installed_version == "new"
    assert record.autostart


async def test_configuration_registration_and_storage_requirements(app_context):
    server = app_context.prepare_server("not_installed")
    assert server.configuration.snapshot().installed_version == "UNKNOWN"
    assert app_context.state.servers.get(server.server_name) is None

    standalone = BedrockServer(
        "standalone", settings=app_context.settings, state=app_context.state
    )
    with pytest.raises(ConfigurationError):
        await standalone.set_autostart(True)
