"""Regression coverage for strict state boundaries and persistence behavior."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.models import GetAllGlobalSettingsRequest
from bedrock_server_manager.api.settings import get_all_global_settings
from bedrock_server_manager.config import bcm_config
from bedrock_server_manager.core.data import ALLOWLIST, PERMISSIONS, ManifestRecord
from bedrock_server_manager.plugins.api_contract import APIResponseValidationError
from bedrock_server_manager.services.plugin_service import PluginService
from bedrock_server_manager.services.settings_service import SettingsService
from bedrock_server_manager.services.user_service import UserService
from bedrock_server_manager.state import AppState, ServerConfigState
from bedrock_server_manager.state.models import RuntimeState, ServerRuntimeInfo
from bedrock_server_manager.state.settings import SettingsState
from bedrock_server_manager.web.tasks import TaskManager


@pytest.mark.parametrize(
    "key,value",
    [
        ("web.port", 0),
        ("web.port", 65536),
        ("web.port", "8080"),
        ("web.port", True),
        ("web.token_expires_weeks", 0),
        ("retention.backups", -1),
        ("retention.downloads", -1),
        ("monitoring.max_retries", -1),
        ("monitoring.process_interval_sec", 0),
        ("monitoring.player_interval_sec", -1),
        ("custom.value", float("nan")),
    ],
)
def test_invalid_settings_never_change_live_state(key, value):
    state = SettingsState()
    before = state.to_dict()
    with pytest.raises(ValidationError):
        state.set(key, value)
    assert state.to_dict() == before
    assert not state.is_dirty


def test_legacy_settings_migrate_without_weakening_new_writes():
    state = SettingsState.from_dict(
        {
            "web.port": "8080",
            "monitoring.max_retiries": "0",
            "retention.backups": "0",
            "extension.value": 42,
        }
    )
    assert state.web.port == 8080
    assert state.monitoring.max_retries == 0
    assert state.retention.backups == 0
    assert state.get("extension.value") == 42
    assert not state.is_dirty
    with pytest.raises(ValidationError):
        state.set("web.port", "8081")


def test_plugin_shorthand_reads_and_writes_use_same_namespace():
    state = SettingsState(plugin_settings={"example": {"enabled": False}})
    state.set("example.enabled", True)
    assert state.get("example.enabled") is True
    assert state.get("plugin_settings.example.enabled") is True
    assert "example" not in state.custom
    assert state.dirty_keys == {"plugin_settings"}


def test_settings_containers_are_snapshots_and_sections_are_frozen():
    state = SettingsState()
    with pytest.raises(ValidationError):
        state.web.port = 9000
    state.custom["bad"] = object()
    assert state.custom == {}
    assert not state.is_dirty
    state.custom = {"good": 42}
    assert state.is_dirty
    with pytest.raises(ValidationError):
        state.custom = {"bad": object()}
    assert state.custom == {"good": 42}


def test_noop_detection_preserves_json_types_and_still_validates():
    state = SettingsState()
    state.set("retention.backups", 1)
    with pytest.raises(ValidationError):
        state.set("retention.backups", True)
    state.set("custom.value", 1)
    assert state.set("custom.value", True)
    assert type(state.get("custom.value")) is bool
    assert not state.set("custom.value", True)


@pytest.mark.parametrize("value", ["true", 1])
def test_persistent_flags_are_strict(value):
    with pytest.raises(ValidationError):
        ServerConfigState.model_validate({"server_name": "example", "autostart": value})


def test_entity_maps_do_not_expose_live_records():
    state = AppState()
    state.servers.set(ServerConfigState(server_name="example", custom={"a": 1}))
    state.servers.clear_dirty()
    state.servers.servers["example"].custom["a"] = object()
    state.servers.servers.clear()
    assert state.servers.get("example").custom == {"a": 1}
    assert not state.servers.is_dirty


def test_runtime_snapshot_is_revalidated_before_storage():
    state = RuntimeState()
    with pytest.raises(ValidationError):
        state.set_server_runtime(
            "example", ServerRuntimeInfo.model_construct(players_online=-1)
        )
    assert "example" not in state.servers


async def test_missing_null_setting_is_persisted(storage):
    state = await storage.load_state()
    await SettingsService(state, storage).update_setting("missing", None)
    loaded = await storage.load_state()
    assert "missing" in loaded.settings.custom
    assert loaded.settings.custom["missing"] is None


async def test_plugin_updates_appear_in_bulk_settings(app_context):
    await app_context.plugin_service.set_setting("example", "value", 42)
    result = await get_all_global_settings(
        GetAllGlobalSettingsRequest(), app_context=app_context
    )
    assert result.settings["plugin_settings"]["example"]["value"] == 42


async def test_nullable_user_fields_can_be_cleared(storage):
    state = await storage.load_state()
    service = UserService(state, storage)
    await service.register_or_update_user("example", email="example@example.com")
    await service.register_or_update_user("example", theme="dark")
    assert state.users.get("example").email == "example@example.com"
    await service.register_or_update_user("example", email=None)
    assert (await storage.load_state()).users.get("example").email is None


async def test_nullable_plugin_fields_can_be_cleared(storage):
    state = await storage.load_state()
    service = PluginService(state, storage)
    await service.register_or_update_plugin("example", author="Author")
    await service.register_or_update_plugin("example", enabled=False)
    assert state.plugins.get("example").author == "Author"
    await service.register_or_update_plugin("example", author=None)
    assert (await storage.load_state()).plugins.get("example").author is None


async def test_deleting_dirty_server_cleans_up_after_commit(storage):
    state = await storage.load_state()
    state.servers.set(ServerConfigState(server_name="example"))
    await storage.flush(state)
    state.servers.set(ServerConfigState(server_name="example", status="PENDING"))
    await storage.delete_server(state, "example")
    await storage.flush(state)
    assert not state.servers.is_dirty
    assert (await storage.load_state()).servers.get("example") is None


async def test_failed_delete_preserves_live_state_and_dirtiness(storage, monkeypatch):
    state = await storage.load_state()
    state.servers.set(ServerConfigState(server_name="example"))
    monkeypatch.setattr(
        storage.server_repo,
        "delete_server",
        AsyncMock(side_effect=RuntimeError("failure")),
    )
    from bedrock_server_manager.error import StorageError

    with pytest.raises(StorageError):
        await storage.delete_server(state, "example")
    assert state.servers.get("example") is not None
    assert "example" in state.servers.dirty_servers


async def test_delete_waits_for_in_flight_flush(storage, monkeypatch):
    state = await storage.load_state()
    state.servers.set(ServerConfigState(server_name="example"))
    entered, release = asyncio.Event(), asyncio.Event()
    save = storage.server_repo.save_server

    async def delayed_save(session, record):
        entered.set()
        await release.wait()
        await save(session, record)

    monkeypatch.setattr(storage.server_repo, "save_server", delayed_save)
    flush = asyncio.create_task(storage.flush(state))
    await entered.wait()
    delete = asyncio.create_task(storage.delete_server(state, "example"))
    await asyncio.sleep(0)
    assert not delete.done()
    release.set()
    await asyncio.wait_for(asyncio.gather(flush, delete), 2)
    assert (await storage.load_state()).servers.get("example") is None
    assert not state.servers.is_dirty


async def test_type_change_during_commit_is_not_acknowledged(storage, monkeypatch):
    state = await storage.load_state()
    state.settings.set("custom.value", 1)
    save = storage.settings_repo.save_settings
    entered, release = asyncio.Event(), asyncio.Event()

    async def delayed_save(session, data):
        entered.set()
        await release.wait()
        await save(session, data)

    monkeypatch.setattr(storage.settings_repo, "save_settings", delayed_save)
    flush = asyncio.create_task(storage.flush(state))
    await entered.wait()
    state.settings.set("custom.value", True)
    release.set()
    await asyncio.wait_for(flush, 2)
    assert state.settings.is_dirty
    await storage.flush(state)
    loaded = await storage.load_state()
    assert type(loaded.settings.get("custom.value")) is bool


@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), {"bad": object()}, {1: "bad"}]
)
async def test_task_validation_is_atomic(value):
    manager = TaskManager(None)

    async def task():
        await asyncio.Event().wait()

    task_id = await manager.run_task(task)
    before = manager.tasks[task_id]
    with pytest.raises(APIResponseValidationError):
        await manager._update_task(task_id, "completed", "Done", value)
    assert manager.tasks[task_id] == before
    await manager.cancel_task(task_id)
    await manager.shutdown()


@pytest.mark.parametrize(
    "field,value", [("data_dir", 42), ("db_url", "invalid"), ("logging_level", "NOPE")]
)
def test_bootstrap_config_rejects_bad_resolved_values(
    field, value, isolated_bcm_config, monkeypatch
):
    from bedrock_server_manager.error import ConfigurationError

    for name in ("BSM_DATA_DIR", "BSM_DB_URL", "BSM_LOG_LEVEL"):
        monkeypatch.delenv(name, raising=False)
    bcm_config.set_custom_data_dir(None)
    bcm_config.set_custom_db_url(None)
    bcm_config.set_custom_log_level(None)
    import json
    from pathlib import Path

    Path(bcm_config.get_config_path()).parent.mkdir(parents=True, exist_ok=True)
    Path(bcm_config.get_config_path()).write_text(json.dumps({field: value}))
    with pytest.raises(ConfigurationError):
        bcm_config.load_config()


def test_minecraft_extensions_are_preserved_and_known_fields_are_strict():
    entry = ALLOWLIST.validate_python([{"name": "Player", "extension": {"a": 1}}])[0]
    assert entry.model_dump()["extension"] == {"a": 1}
    with pytest.raises(ValidationError):
        ALLOWLIST.validate_python([{"name": "Player", "ignoresPlayerLimit": "true"}])
    assert (
        PERMISSIONS.validate_python([{"xuid": "1", "permission": "OPERATOR"}])[
            0
        ].permission
        == "operator"
    )
    manifest = {
        "header": {"uuid": "example", "name": "Example", "version": [1, 0, 0]},
        "modules": [{"type": "data", "extension": True}],
        "extension": {"a": 1},
    }
    assert ManifestRecord.model_validate(manifest).model_dump()["extension"] == {"a": 1}
    manifest["header"]["version"] = [True, 0, 0]
    with pytest.raises(ValidationError):
        ManifestRecord.model_validate(manifest)
