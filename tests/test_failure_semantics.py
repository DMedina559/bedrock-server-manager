"""Integration coverage for truthful results and recovery after I/O failures."""

import asyncio
import importlib
import io
from pathlib import Path

import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.backup_restore import backup_all
from bedrock_server_manager.api.misc import prune_download_cache
from bedrock_server_manager.api.models import (
    AddPlayersManuallyRequest,
    BackupAllRequest,
    PruneDownloadCacheRequest,
    SendToClientRequest,
)
from bedrock_server_manager.api.models.tasks import TaskSnapshot
from bedrock_server_manager.api.player import add_players_manually
from bedrock_server_manager.api.server import server_lifecycle_manager
from bedrock_server_manager.api.websocket import send_to_client
from bedrock_server_manager.contracts import ComponentResults, FailedItem, FailureInfo
from bedrock_server_manager.error import (
    DependencyUnavailableError,
    IncompleteOperationError,
    ServerStopError,
    StorageError,
    UserInputError,
)


async def test_failed_stop_retains_process_and_runtime(
    real_bedrock_server, monkeypatch
):
    class BrokenPipe:
        def write(self, data):
            raise RuntimeError("command channel failure")

    class UnkillableProcess(asyncio.subprocess.Process):
        pid = 999999
        returncode = None
        stdin = BrokenPipe()

        def __init__(self):
            pass

        def kill(self):
            raise PermissionError("cannot kill process")

    server = real_bedrock_server
    process = UnkillableProcess()
    with monkeypatch.context() as fault:
        fault.setattr(server.process, "_process", process)
        with pytest.raises(ServerStopError):
            await server.stop()
        assert server.process._process is process
        assert server.state.runtime.get_server_runtime(server.server_name).running
        assert await server.get_status_from_config() == "RUNNING"


async def test_forced_stop_waits_for_exit(real_bedrock_server, monkeypatch):
    class DelayedProcess(asyncio.subprocess.Process):
        pid = 999998
        returncode = None
        stdin = None
        killed = False

        def __init__(self):
            pass

        def kill(self):
            self.killed = True

        async def wait(self):
            assert self.killed
            self.returncode = -9

    process = DelayedProcess()
    with monkeypatch.context() as fault:
        fault.setattr(real_bedrock_server.process, "_process", process)
        await real_bedrock_server.stop()
        assert process.returncode == -9
        assert real_bedrock_server.process._process is None
        assert not real_bedrock_server.state.runtime.get_server_runtime(
            real_bedrock_server.server_name
        ).running


async def test_failed_probe_cannot_select_offline_world_export(
    populated_server, tmp_path, monkeypatch
):
    world = await populated_server.get_world_name()

    async def unavailable():
        raise DependencyUnavailableError("Process inspection unavailable")

    with monkeypatch.context() as fault:
        fault.setattr(populated_server, "is_running", unavailable)
        target = tmp_path / "unsafe.mcworld"
        with pytest.raises(DependencyUnavailableError):
            await populated_server.worlds.export_world(world, str(target))
        assert not target.exists()


async def test_failed_capture_does_not_publish_a_partial_archive(
    app_context, populated_server, monkeypatch
):
    def fail_copy(*args, **kwargs):
        raise PermissionError("Cannot read source")

    monkeypatch.setattr("bedrock_server_manager.backups.server.copy_source", fail_copy)
    with pytest.raises(PermissionError):
        await backup_all(
            BackupAllRequest(server_name=populated_server.server_name),
            app_context=app_context,
        )
    assert await populated_server.backups.list_snapshots() == []


async def test_retention_failure_is_not_success(app_context, tmp_path, monkeypatch):
    module = importlib.import_module("bedrock_server_manager.core.downloader")
    archive = tmp_path / "bedrock-server-1.0.zip"
    archive.write_bytes(b"archive")
    original = module.os.remove

    def deny_remove(path, *args, **kwargs):
        if str(path) == str(archive):
            raise PermissionError("Cannot remove archive")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(module.os, "remove", deny_remove)
    with pytest.raises(IncompleteOperationError) as captured:
        await prune_download_cache(
            PruneDownloadCacheRequest(download_dir=str(tmp_path), keep_count=0),
            app_context=app_context,
        )
    assert archive.exists()
    assert str(archive) in captured.value.result.failures


async def test_failed_upload_preserves_previous_archive(
    app_context, plugin_factory, valid_mcworld_zip, monkeypatch
):
    from fastapi import UploadFile

    from bedrock_server_manager.core import files
    from bedrock_server_manager.plugins.default import content_uploader_plugin

    plugin = await plugin_factory(
        "atomic_uploader", Path(content_uploader_plugin.__file__).read_text()
    )
    destination = plugin.content_directory / "worlds" / "existing.mcworld"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(b"previous valid archive")
    original = files.os.replace

    def deny_replace(source, target):
        if Path(target) == destination:
            raise OSError("Cannot replace archive")
        return original(source, target)

    monkeypatch.setattr(files.os, "replace", deny_replace)
    endpoint = next(
        route.endpoint
        for route in plugin.router.routes
        if route.path == "/api/content/upload"
    )
    upload = UploadFile(
        filename="existing.mcworld",
        file=io.BytesIO(Path(valid_mcworld_zip).read_bytes()),
    )
    with pytest.raises(OSError):
        await endpoint(request=None, file=upload, current_user=None)
    assert destination.read_bytes() == b"previous valid archive"
    assert upload.file.closed
    assert not list(destination.parent.glob("bsm-upload-*"))


async def test_invalid_upload_cannot_replace_valid_archive(plugin_factory):
    from fastapi import UploadFile

    from bedrock_server_manager.plugins.default import content_uploader_plugin

    plugin = await plugin_factory(
        "invalid_uploader", Path(content_uploader_plugin.__file__).read_text()
    )
    destination = plugin.content_directory / "worlds" / "existing.mcworld"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(b"previous archive")
    endpoint = next(
        route.endpoint
        for route in plugin.router.routes
        if route.path == "/api/content/upload"
    )
    with pytest.raises(UserInputError):
        await endpoint(
            request=None,
            file=UploadFile(
                filename="existing.mcworld", file=io.BytesIO(b"invalid archive")
            ),
            current_user=None,
        )
    assert destination.read_bytes() == b"previous archive"


async def test_missing_ban_uses_not_found(admin_auth_client, real_bedrock_server):
    response = await admin_auth_client.request(
        "DELETE",
        f"/api/server/{real_bedrock_server.server_name}/bans/remove",
        json={"xuid": "missing"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_restart_error_does_not_replace_original(
    app_context, real_bedrock_server, monkeypatch
):
    from bedrock_server_manager.api import server as api

    async def running():
        return True

    async def stop(*args, **kwargs):
        return None

    async def start(*args, **kwargs):
        raise RuntimeError("Restart failed")

    with monkeypatch.context() as fault:
        fault.setattr(real_bedrock_server, "is_running", running)
        fault.setattr(api, "stop_server", stop)
        fault.setattr(api, "start_server", start)
        with pytest.raises(UserInputError, match="Original operation") as captured:
            async with server_lifecycle_manager(
                real_bedrock_server.server_name, True, app_context=app_context
            ):
                raise UserInputError("Original operation")
        assert any("restart also failed" in note for note in captured.value.__notes__)


async def test_player_counts_follow_parsing_and_storage(app_context):
    request = AddPlayersManuallyRequest(
        player_strings=["Steve:123,Alex:456", "Renamed:123"]
    )
    result = await add_players_manually(request, app_context=app_context)
    assert (
        result.submitted_count,
        result.parsed_count,
        result.unique_count,
        result.count,
    ) == (2, 3, 2, 2)
    assert {
        player["xuid"]: player["name"]
        for player in await app_context.storage.get_all_players()
    } == {"123": "Renamed", "456": "Alex"}
    assert (await add_players_manually(request, app_context=app_context)).count == 0


async def test_missing_socket_reports_unavailable(app_context):
    result = await send_to_client(
        SendToClientRequest(client_id="missing", data={"message": "hello"}),
        app_context=app_context,
    )
    assert result.status == "skipped"
    assert result.delivery.sent == 0 and result.delivery.unavailable == 1


@pytest.mark.parametrize(
    "service,method,args",
    [
        ("server_service", "register_or_update_server", ("new_server",)),
        ("user_service", "register_or_update_user", ("new_user",)),
        ("plugin_service", "register_or_update_plugin", ("new_plugin",)),
    ],
)
async def test_failed_service_commit_does_not_publish(
    app_context, monkeypatch, service, method, args
):
    from sqlalchemy.ext.asyncio import AsyncSession

    async def fail_commit(session):
        raise RuntimeError("Commit failed")

    monkeypatch.setattr(AsyncSession, "commit", fail_commit)
    with pytest.raises(StorageError):
        await getattr(getattr(app_context, service), method)(*args)
    container = {
        "server_service": app_context.state.servers,
        "user_service": app_context.state.users,
        "plugin_service": app_context.state.plugins,
    }[service]
    assert container.get(args[0]) is None


async def test_failed_settings_commit_preserves_previous_value(
    app_context, monkeypatch
):
    from sqlalchemy.ext.asyncio import AsyncSession

    before = app_context.settings.get("web.port")

    async def fail_commit(session):
        raise RuntimeError("Commit failed")

    with monkeypatch.context() as fault:
        fault.setattr(AsyncSession, "commit", fail_commit)
        with pytest.raises(StorageError):
            await app_context.settings.set("web.port", before + 1)
        assert app_context.settings.get("web.port") == before


@pytest.mark.parametrize(
    "status,result,error",
    [
        ("completed", None, FailureInfo(code="internal_error", message="Failed")),
        ("failed", None, None),
        ("running", 42, None),
    ],
)
def test_task_contract_rejects_contradictory_states(status, result, error):
    with pytest.raises(ValidationError):
        TaskSnapshot(
            id="task", status=status, message="State", result=result, error=error
        )


def test_component_failure_round_trip_requires_error():
    with pytest.raises(ValidationError):
        FailedItem()
    result = ComponentResults(
        components={
            "world": FailedItem(
                error=FailureInfo(code="internal_error", message="Failed")
            )
        }
    )
    assert ComponentResults.model_validate_json(result.model_dump_json()) == result


async def test_process_info_failure_propagates(real_bedrock_server, monkeypatch):
    module = importlib.import_module("bedrock_server_manager.core.server.process")

    async def failed_probe(*args, **kwargs):
        raise DependencyUnavailableError("probe failed")

    with monkeypatch.context() as fault:
        fault.setattr(
            module.system_process, "get_verified_bedrock_process", failed_probe
        )
        with pytest.raises(DependencyUnavailableError):
            await real_bedrock_server.process.get_process_info()
