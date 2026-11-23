from pathlib import Path

import pytest

from bedrock_server_manager.api.install import install_new_server, update_server
from bedrock_server_manager.api.models import (
    InstallNewServerRequest,
    UpdateServerRequest,
)
from bedrock_server_manager.error import BSMError, UserInputError


async def test_custom_install_creates_runnable_persisted_server(
    app_context, custom_server_archive
):
    request = InstallNewServerRequest(
        server_name="installed",
        target_version="CUSTOM",
        server_zip_path=str(custom_server_archive),
    )
    response = await install_new_server(request, app_context=app_context)
    assert response.status == "success"
    server = app_context.get_server("installed")
    assert await server.is_installed()
    assert Path(server.paths.bedrock_executable_path).is_file()
    assert response.version == await server.get_version()
    with pytest.raises(UserInputError):
        await install_new_server(request, app_context=app_context)
    await server.set_target_version(response.version)
    response = await update_server(
        UpdateServerRequest(server_name="installed"), app_context=app_context
    )
    assert response.status == "success"
    assert response.updated is False


async def test_missing_custom_archive_does_not_install(app_context, tmp_path):
    with pytest.raises(BSMError):
        await install_new_server(
            InstallNewServerRequest(
                server_name="missing",
                target_version="CUSTOM",
                server_zip_path=str(tmp_path / "missing.zip"),
            ),
            app_context=app_context,
        )
    assert not await app_context.prepare_server("missing").is_installed()


async def test_update_downloads_real_archive_and_preserves_world(
    app_context, dummy_server_zip, tmp_path, valid_mcworld_zip, download_api
):
    archive = dummy_server_zip(target_dir=tmp_path, version="1.20.1.1")
    await install_new_server(
        InstallNewServerRequest(
            server_name="updated", target_version="CUSTOM", server_zip_path=str(archive)
        ),
        app_context=app_context,
    )
    server = app_context.get_server("updated")
    await server.worlds.extract_mcworld(
        str(valid_mcworld_zip), await server.get_world_name()
    )
    marker = (
        Path(server.paths.server_dir)
        / "worlds"
        / await server.get_world_name()
        / "integration.txt"
    )
    marker.write_text("keep world")
    await server.set_target_version("LATEST")
    response = await update_server(
        UpdateServerRequest(server_name="updated"), app_context=app_context
    )
    assert response.updated is True
    assert response.new_version == "1.26.45.1"
    assert marker.read_text() == "keep world"
    assert list(Path(server.backups.server_backup_directory).glob("*.bsmbackup"))


async def test_failed_pre_update_backup_prevents_install(
    app_context, populated_server, download_api, monkeypatch
):
    server = populated_server
    await server.set_version("1.20.1.1")

    async def failed_capture(**kwargs):
        assert kwargs["purpose"] == "pre_update"
        raise OSError("Backup disk unavailable")

    monkeypatch.setattr(server.backups, "create_snapshot", failed_capture)
    with pytest.raises(OSError, match="Backup disk unavailable"):
        await update_server(
            UpdateServerRequest(server_name=server.server_name, send_message=False),
            app_context=app_context,
        )
    assert await server.get_version() == "1.20.1.1"


async def test_cancellation_after_file_commit_keeps_version_metadata_consistent(
    app_context, populated_server, monkeypatch
):
    import asyncio

    from bedrock_server_manager.core.server.software import install_or_update

    async def needs_update(*args, **kwargs):
        return True

    async def committed_then_cancelled(self, is_update):
        self.actual_version = "1.26.45.1"
        self.installation_committed = True
        raise asyncio.CancelledError

    monkeypatch.setattr(
        "bedrock_server_manager.core.server.software.is_update_needed", needs_update
    )
    monkeypatch.setattr(
        "bedrock_server_manager.core.downloader.BedrockDownloader.full_server_setup",
        committed_then_cancelled,
    )
    with pytest.raises(asyncio.CancelledError):
        await install_or_update(populated_server, "LATEST")
    assert await populated_server.get_version() == "1.26.45.1"
    assert not await populated_server.is_running()
