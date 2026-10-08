from pathlib import Path

import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.install import install_new_server, update_server
from bedrock_server_manager.api.models import (
    InstallNewServerRequest,
    UpdateServerRequest,
)
from bedrock_server_manager.error import BSMError, UserInputError


async def test_custom_install_creates_runnable_persisted_server(
    app_context, dummy_server_zip, tmp_path
):
    archive = dummy_server_zip(target_dir=tmp_path, version="1.26.45.1")
    request = InstallNewServerRequest(
        server_name="installed", target_version="CUSTOM", server_zip_path=str(archive)
    )
    response = await install_new_server(request, app_context=app_context)
    assert response.status == "success"
    server = app_context.get_server("installed")
    assert await server.is_installed()
    assert Path(server.bedrock_executable_path).is_file()
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
    assert not await app_context.get_server("missing").is_installed()


@pytest.mark.parametrize("name", ["", "../outside", "invalid name"])
def test_install_rejects_invalid_server_names(name):
    with pytest.raises(ValidationError):
        InstallNewServerRequest(server_name=name)


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
    await server.extract_mcworld(str(valid_mcworld_zip), await server.get_world_name())
    marker = (
        Path(server.server_dir)
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
    assert list(Path(server.server_backup_directory).glob("*.mcworld"))
