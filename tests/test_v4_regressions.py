import asyncio
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.models import StartServerResponse
from bedrock_server_manager.services.plugin_service import PluginService
from bedrock_server_manager.services.server_service import ServerService
from bedrock_server_manager.services.user_service import UserService
from bedrock_server_manager.state import AppState
from bedrock_server_manager.state.settings import SettingsState
from bedrock_server_manager.web.tasks import TaskManager


def test_settings_reject_invalid_update_atomically():
    state = SettingsState()
    original = state.model_dump()
    with pytest.raises(ValidationError):
        state.set("web.port", "invalid")
    assert state.model_dump() == original
    assert not state.is_dirty
    with pytest.raises(ValidationError):
        state.set("web.porrt", 9000)
    assert state.model_dump() == original
    state.set("nullable", None)
    assert "nullable" in state.custom
    state.set("plugin_settings", {"a.b": {"enabled": False}})
    assert state.plugin_settings == {"a.b": {"enabled": False}}
    assert state.get("model_dump") is None


async def test_plugin_settings_keep_dotted_identity_and_snapshot_isolation():
    state = AppState()
    storage = AsyncMock()
    service = PluginService(state, storage)
    await service.set_setting("a.b", "nested.value", [False, 0])
    assert service.get_setting("a.b", "nested.value") == [False, 0]
    assert service.get_setting("a", "b.nested.value") is None
    value = service.get_setting("a.b", "nested.value")
    value.append(1)
    assert service.get_setting("a.b", "nested.value") == [False, 0]
    await service.register_or_update_plugin("a.b", enabled=False)
    assert service.get_setting("a.b", "nested.value") == [False, 0]


async def test_partial_updates_preserve_existing_fields():
    state = AppState()
    storage = AsyncMock()
    servers = ServerService(state, storage)
    users = UserService(state, storage)
    await servers.register_or_update_server(
        "example", installed_version="1.2", status="RUNNING"
    )
    await servers.register_or_update_server("example")
    assert state.servers.get("example").installed_version == "1.2"
    assert state.servers.get("example").status == "RUNNING"
    await users.register_or_update_user(
        "owner", role="admin", theme="dark", is_active=False
    )
    await users.register_or_update_user("owner")
    assert state.users.get("owner").role == "admin"
    assert state.users.get("owner").theme == "dark"
    assert state.users.get("owner").is_active is False


async def test_task_owner_and_disconnected_notification():
    connection = AsyncMock()
    connection.send_to_user.side_effect = RuntimeError("Disconnected")
    manager = TaskManager(connection)

    async def operation():
        return StartServerResponse(
            server_name="example", outcome="started", message="Started"
        )

    task_id = await manager.run_task(operation, "owner")
    await manager.shutdown()
    snapshot = await manager.get_task(task_id, username="owner")
    assert snapshot.status == "completed"
    assert snapshot.result["outcome"] == "started"
    assert await manager.get_task(task_id, username="other") is None
    assert await manager.get_all_tasks(username="other") == {}


async def test_active_task_capacity_preserves_running_handle():
    manager = TaskManager(None)
    manager._max_tasks = 1
    gate = asyncio.Event()
    task_id = await manager.run_task(gate.wait)
    with pytest.raises(RuntimeError):
        await manager.run_task(gate.wait)
    assert task_id in manager.futures
    gate.set()
    await manager.shutdown()


def test_generated_plugin_api_matches_registry():
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    subprocess.run(
        [sys.executable, str(root / "scripts/generate_plugin_api.py"), "--check"],
        cwd=root,
        check=True,
        capture_output=True,
    )


async def test_runtime_lifecycle_positional_options_match_protocol():
    from unittest.mock import MagicMock

    from bedrock_server_manager.plugins.api_bridge import create_app_api

    context = MagicMock()
    api = create_app_api("example", context)
    async with api.runtime.server_lifecycle_manager("server", False, False):
        pass
    context.get_server.assert_called_once_with("server")
    with pytest.raises(TypeError):
        api.runtime.server_lifecycle_manager("server", False, app_context=context)


def test_legacy_monitoring_key_is_normalized_on_load():
    settings = SettingsState.from_dict({"monitoring.max_retiries": 7})
    assert settings.monitoring.max_retries == 7
    assert "max_retiries" not in settings.to_dict()["monitoring"]


async def test_invalid_task_output_is_an_internal_error():
    manager = TaskManager(None)

    async def operation():
        return object()

    task_id = await manager.run_task(operation)
    await manager.shutdown()
    snapshot = await manager.get_task(task_id)
    assert snapshot.status == "failed"
    assert snapshot.result is None
    assert snapshot.error.code == "internal_error"
