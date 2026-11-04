"""Capabilities keep the same authority across direct, runtime and scheduled calls."""

from functools import wraps
from types import SimpleNamespace

import pytest

from bedrock_server_manager.api.models import GetPluginStatusesRequest
from bedrock_server_manager.api.plugins import get_plugin_statuses
from bedrock_server_manager.plugins.api_bridge import _api_registry, create_app_api
from bedrock_server_manager.plugins.scopes import (
    VALID_PERMISSION_SCOPES,
    normalize_permissions,
    plugin_permissions,
)


async def make_plugin(plugin_factory, name="capability_probe", permissions=None):
    return await plugin_factory(
        name,
        f"""
from bedrock_server_manager import PluginBase
class Probe(PluginBase):
    version = "1.0"
    permissions = {permissions!r}
""",
    )


def spy_api(monkeypatch, name):
    entry = _api_registry[name]
    calls = []

    @wraps(entry[0])
    async def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(status="success")

    monkeypatch.setitem(_api_registry, name, (spy, *entry[1:]))
    return spy, calls


@pytest.mark.parametrize(
    "value",
    [
        "servers:command",
        {"servers:command": True},
        [None],
        [1],
        [""],
        [" servers:command"],
    ],
)
def test_malformed_declarations_are_rejected(value):
    with pytest.raises(TypeError):
        normalize_permissions(value)


def test_permission_catalog_mapping_is_consistent():
    create_app_api("catalog", None)
    assert dict(VALID_PERMISSION_SCOPES) == VALID_PERMISSION_SCOPES.copy()
    assert len(VALID_PERMISSION_SCOPES) == len(dict(VALID_PERMISSION_SCOPES))
    assert VALID_PERMISSION_SCOPES == dict(VALID_PERMISSION_SCOPES)
    assert "downloads:prune" in VALID_PERMISSION_SCOPES


async def test_permissions_are_snapshotted_and_status_preserves_empty_override(
    app_context, plugin_factory
):
    plugin = await plugin_factory(
        "empty_override",
        """
from bedrock_server_manager import PluginBase
class Probe(PluginBase):
    version = "1.0"
    permissions = ["servers:command"]
    def __init__(self, *args):
        super().__init__(*args)
        self.permissions = []
""",
    )
    plugin.permissions.append("servers:command")
    assert plugin_permissions(plugin) == frozenset()
    status = await get_plugin_statuses(
        GetPluginStatusesRequest(), app_context=app_context
    )
    assert status.plugins["empty_override"].permissions == []
    with pytest.raises(PermissionError, match="servers:command"):
        await plugin.api.server.send_command({"server_name": "test", "command": "list"})


@pytest.mark.parametrize(
    "name",
    [
        "restore_all",
        "restore_world",
        "restore_config_file",
        "prune_old_backups",
        "prune_download_cache",
        "websocket_broadcast",
        "websocket_send_to_user",
        "websocket_send_to_client",
        "websocket_publish_ws_event",
    ],
)
async def test_sensitive_apis_deny_before_dispatch(plugin_factory, monkeypatch, name):
    plugin = await make_plugin(plugin_factory, permissions=[])
    _, calls = spy_api(monkeypatch, name)
    domain = _api_registry[name][4]
    from bedrock_server_manager.plugins.api_types import API_METHODS

    method = next(k for k, v in API_METHODS[domain].items() if v == name)
    with pytest.raises(PermissionError):
        await getattr(getattr(plugin.api, domain), method)({})
    assert not calls


@pytest.mark.parametrize("as_callable", [False, True])
async def test_schedules_enforce_plugin_permissions_at_execution(
    app_context, plugin_factory, monkeypatch, as_callable
):
    plugin = await make_plugin(plugin_factory, permissions=[])
    spy, calls = spy_api(monkeypatch, "send_command")
    task = plugin.api.runtime.register_api_task(
        "command", spy if as_callable else "server.send_command"
    )
    with pytest.raises(PermissionError, match="servers:command"):
        await task.handler(server_name="test", options={"command": "list"})
    assert not calls
    granted = await make_plugin(plugin_factory, "granted_probe", ["servers:command"])
    task = granted.api.runtime.register_api_task(
        "command", spy if as_callable else "server.send_command"
    )
    await task.handler(server_name="test", options={"command": "list"})
    assert len(calls) == 1
    app_context.events.remove_owner("plugin:granted_probe")
    app_context.events.open_owner("plugin:granted_probe")
    with pytest.raises(RuntimeError, match="owner"):
        await task.handler(server_name="test", options={"command": "list"})
    assert len(calls) == 1


@pytest.mark.parametrize("as_callable", [False, True])
async def test_schedules_reject_internal_methods_but_core_can_execute(
    app_context, plugin_factory, monkeypatch, as_callable
):
    plugin = await make_plugin(plugin_factory)
    spy, calls = spy_api(monkeypatch, "delete_server_data")
    target = spy if as_callable else "server.delete_server_data"
    with pytest.raises(AttributeError, match="not exposed"):
        plugin.api.runtime.register_api_task("delete", target)
    task = app_context.scheduler.tasks.register_api_task("system:delete", target)
    await task.handler(server_name="test", options={})
    assert len(calls) == 1


async def test_custom_plugin_schedule_cannot_request_app_context(plugin_factory):
    plugin = await make_plugin(plugin_factory)

    async def callback(request, *, app_context):
        raise AssertionError("must not execute")

    with pytest.raises(TypeError, match="application context"):
        plugin.api.runtime.register_api_task("custom", callback)


async def test_old_api_and_runtime_handles_stay_invalid_after_reload(
    app_context, plugin_factory
):
    plugin = await make_plugin(plugin_factory, permissions=["servers:lifecycle"])
    read = plugin.api.settings.get_all_global_settings
    path = plugin.api.runtime.get_plugin_data_path
    cm = plugin.api.runtime.server_lifecycle_manager("test", stop_before=True)
    app_context.events.remove_owner("plugin:capability_probe")
    app_context.events.open_owner("plugin:capability_probe")
    for call in (lambda: read({}), lambda: path()):
        with pytest.raises(RuntimeError, match="owner"):
            await call()
    with pytest.raises(RuntimeError, match="owner"):
        async with cm:
            raise AssertionError("must not enter")


async def test_lifecycle_runtime_requires_scope_before_touching_server(
    app_context, plugin_factory, monkeypatch
):
    plugin = await make_plugin(plugin_factory, permissions=[])
    from unittest.mock import Mock

    get_server = Mock(side_effect=AssertionError("must not access server"))
    monkeypatch.setattr(app_context, "get_server", get_server)
    with pytest.raises(PermissionError, match="servers:lifecycle"):
        async with plugin.api.runtime.server_lifecycle_manager(
            "test", stop_before=True
        ):
            pass
    get_server.assert_not_called()


async def test_websocket_provider_removal_checks_owner(app_context, plugin_factory):
    plugin = await make_plugin(plugin_factory)
    manager = app_context.connection_manager
    manager.register_data_provider("foreign", lambda: {}, plugin_name="other")
    manager.register_data_provider("mine", lambda: {}, plugin_name="capability_probe")
    manager.register_data_provider("core", lambda: {})
    for topic in ("foreign", "core"):
        with pytest.raises(PermissionError, match="own"):
            await plugin.api.runtime.register_data_provider(topic, lambda: {})
        with pytest.raises(PermissionError, match="own"):
            await plugin.api.websocket.websocket_unregister_data_provider(
                {"topic": topic}
            )
        assert topic in manager.data_providers
    result = await plugin.api.websocket.websocket_unregister_data_provider(
        {"topic": "mine"}
    )
    assert result.outcome == "removed"
    assert manager.unregister_data_provider("foreign")
    result = await app_context.api.websocket.websocket_unregister_data_provider(
        {"topic": "core"}
    )
    assert result.outcome == "removed"


async def test_plugin_cleanup_is_confined_to_download_cache(
    app_context, plugin_factory, tmp_path, monkeypatch
):
    from unittest.mock import AsyncMock

    from bedrock_server_manager.contracts import CleanupResult

    plugin = await make_plugin(plugin_factory, permissions=["downloads:prune"])
    cleaner = AsyncMock(return_value=CleanupResult())
    from bedrock_server_manager.api import misc

    monkeypatch.setattr(misc, "prune_old_downloads", cleaner)
    with pytest.raises(PermissionError, match="download cache"):
        await plugin.api.misc.prune_download_cache(
            {"download_dir": str(tmp_path / "outside")}
        )
    cleaner.assert_not_awaited()
    root = app_context.settings.get("paths.downloads")
    await plugin.api.misc.prune_download_cache({"download_dir": root})
    assert cleaner.await_count == 1
    # Core callers retain their explicit-directory behavior.
    await app_context.api.misc.prune_download_cache(
        {"download_dir": str(tmp_path / "outside")}
    )
    assert cleaner.await_count == 2


async def test_invalid_declaration_does_not_abort_discovery(
    app_context, plugin_factory
):
    healthy = await make_plugin(plugin_factory, "healthy_probe", [])
    directory = app_context.plugin_manager.plugin_dirs[0]
    (directory / "malformed.py").write_text(
        'from bedrock_server_manager import PluginBase\nclass Broken(PluginBase):\n    version="1.0"\n    permissions="servers:command"\n'
    )
    await app_context.plugin_manager._synchronize_config_with_disk()
    assert app_context.plugin_manager.get_plugin_status("malformed") == "ERROR"
    assert app_context.plugin_manager.get_plugin("healthy_probe") is healthy
    response = await get_plugin_statuses(
        GetPluginStatusesRequest(), app_context=app_context
    )
    assert response.plugins["malformed"].permissions == []


async def test_lifecycle_runtime_with_permission_stops_and_restarts(
    app_context, plugin_factory, monkeypatch
):
    from unittest.mock import AsyncMock

    from bedrock_server_manager.api import server

    plugin = await make_plugin(plugin_factory, permissions=["servers:lifecycle"])
    monkeypatch.setattr(
        app_context,
        "get_server",
        lambda *a, **k: SimpleNamespace(is_running=AsyncMock(return_value=True)),
    )
    stop, start = AsyncMock(), AsyncMock()
    monkeypatch.setattr(server, "stop_server", stop)
    monkeypatch.setattr(server, "start_server", start)
    async with plugin.api.runtime.server_lifecycle_manager("test", stop_before=True):
        assert stop.await_count == 1
    assert start.await_count == 1


def test_pruning_uses_maintenance_scopes():
    assert _api_registry["prune_download_cache"][5] == "downloads:prune"
    assert _api_registry["prune_old_backups"][5] == "backups:prune"
    assert _api_registry["manage_server_snapshot"][5] == "backups:manage"


async def test_download_cleanup_rejects_symlink_escape(
    app_context, plugin_factory, tmp_path, monkeypatch
):
    from pathlib import Path
    from unittest.mock import AsyncMock

    from bedrock_server_manager.api import misc

    plugin = await make_plugin(plugin_factory, permissions=["downloads:prune"])
    root = Path(app_context.settings.get("paths.downloads"))
    root.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    link = root / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Creating symlinks requires platform support/privileges")
    cleaner = AsyncMock()
    monkeypatch.setattr(misc, "prune_old_downloads", cleaner)
    with pytest.raises(PermissionError, match="download cache"):
        await plugin.api.misc.prune_download_cache({"download_dir": str(link)})
    cleaner.assert_not_awaited()


async def test_path_permission_checks_share_the_load_time_snapshot(plugin_factory):
    plugin = await make_plugin(plugin_factory, permissions=[])
    plugin.permissions.append("path:servers")
    for call in (
        lambda: plugin.api.runtime.get_system_path("servers"),
        lambda: plugin.api.settings.get_global_setting({"key": "paths.servers"}),
    ):
        with pytest.raises(PermissionError, match="path:servers"):
            await call()
    settings = await plugin.api.settings.get_all_global_settings({})
    assert "paths" not in settings.settings


@pytest.mark.parametrize(
    "declaration,allowed",
    [
        ("omitted", True),
        (None, True),
        ([], False),
        (["servers:command", "servers:lifecycle", "path:servers"], True),
    ],
)
async def test_legacy_and_explicit_permission_modes_match_all_dispatch_paths(
    app_context, plugin_factory, monkeypatch, declaration, allowed
):
    from pathlib import Path
    from unittest.mock import AsyncMock

    line = "" if declaration == "omitted" else f"    permissions = {declaration!r}\n"
    plugin = await plugin_factory(
        "compatibility_probe",
        'from bedrock_server_manager import PluginBase\nclass Probe(PluginBase):\n    version = "1.0"\n'
        + line,
    )
    _, calls = spy_api(monkeypatch, "send_command")
    task = plugin.api.runtime.register_api_task("command", "server.send_command")
    command = {"server_name": "test", "command": "list"}
    operations = [
        lambda: plugin.api.server.send_command(command),
        lambda: task.handler(server_name="test", options={"command": "list"}),
        lambda: plugin.api.runtime.get_system_path("servers"),
        lambda: plugin.api.settings.get_global_setting({"key": "paths.servers"}),
    ]
    for operation in operations:
        if allowed:
            await operation()
        else:
            with pytest.raises(PermissionError):
                await operation()
    assert len(calls) == (2 if allowed else 0)
    settings = await plugin.api.settings.get_all_global_settings({})
    assert ("servers" in settings.settings.get("paths", {})) is allowed
    if allowed:
        assert (
            await plugin.api.runtime.get_system_path("servers")
            == Path(app_context.settings.get("paths.servers")).resolve()
        )
    monkeypatch.setattr(
        app_context,
        "get_server",
        lambda *a, **k: SimpleNamespace(is_running=AsyncMock(return_value=False)),
    )
    if allowed:
        async with plugin.api.runtime.server_lifecycle_manager(
            "test", stop_before=False
        ):
            pass
    else:
        with pytest.raises(PermissionError, match="servers:lifecycle"):
            async with plugin.api.runtime.server_lifecycle_manager(
                "test", stop_before=False
            ):
                pass


@pytest.mark.parametrize("declaration,allowed", [(None, True), ([], False)])
async def test_legacy_mode_is_snapshotted_until_reload(
    plugin_factory, monkeypatch, declaration, allowed
):
    plugin = await make_plugin(plugin_factory, permissions=declaration)
    plugin.permissions = [] if declaration is None else None
    _, calls = spy_api(monkeypatch, "send_command")
    if allowed:
        await plugin.api.server.send_command({"server_name": "test", "command": "list"})
    else:
        with pytest.raises(PermissionError):
            await plugin.api.server.send_command(
                {"server_name": "test", "command": "list"}
            )
    assert len(calls) == int(allowed)


def test_absent_plugin_is_not_treated_as_legacy():
    from bedrock_server_manager.plugins.scopes import plugin_has_permission

    assert not plugin_has_permission(None, "servers:command")
    assert normalize_permissions(None) is None
    assert normalize_permissions([]) == frozenset()


@pytest.mark.parametrize("explicit_none", [False, True])
async def test_legacy_mode_survives_metadata_sync_and_reload(
    app_context, plugin_factory, monkeypatch, explicit_none
):
    source = 'from bedrock_server_manager import PluginBase\nclass Legacy(PluginBase):\n    version = "1.0"\n'
    if explicit_none:
        source += "    permissions = None\n"
    plugin = await plugin_factory("legacy_probe", source)
    _, calls = spy_api(monkeypatch, "send_command")
    old_call = plugin.api.server.send_command
    status = await get_plugin_statuses(
        GetPluginStatusesRequest(), app_context=app_context
    )
    assert status.plugins["legacy_probe"].permissions == []
    assert await app_context.plugin_manager.reload_plugin("legacy_probe")
    reloaded = app_context.plugin_manager.get_plugin("legacy_probe")
    await reloaded.api.server.send_command({"server_name": "test", "command": "list"})
    assert len(calls) == 1
    with pytest.raises(RuntimeError, match="owner"):
        await old_call({"server_name": "test", "command": "list"})
