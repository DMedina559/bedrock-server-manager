import os

import aiofiles.ospath
import pytest

from bedrock_server_manager.core.server.removal import (
    delete_all_data,
    delete_server_files,
    set_filesystem_permissions,
)
from bedrock_server_manager.error import AppFileNotFoundError


async def test_installation_validation_permissions_and_deletion(real_bedrock_server):
    """Test installation checks, permissions, missing files, and deletion."""
    server = real_bedrock_server

    assert await server.is_installed() is True
    assert await server.validate_installation() is True

    await set_filesystem_permissions(server)
    assert os.access(server.paths.bedrock_executable_path, os.R_OK | os.X_OK)

    # Missing properties invalidates installation
    props_bytes = open(server.paths.server_properties_path, "rb").read()
    os.remove(server.paths.server_properties_path)
    assert not await server.is_installed()
    with pytest.raises(AppFileNotFoundError):
        await server.validate_installation()
    with open(server.paths.server_properties_path, "wb") as f:
        f.write(props_bytes)

    # Missing executable invalidates installation
    exe_bytes = open(server.paths.bedrock_executable_path, "rb").read()
    os.remove(server.paths.bedrock_executable_path)
    assert await server.is_installed() is False
    with pytest.raises(AppFileNotFoundError):
        await server.validate_installation()
    with open(server.paths.bedrock_executable_path, "wb") as f:
        f.write(exe_bytes)

    # Delete server files and then delete all data (including config and DB record)
    world_dir = os.path.join(server.paths.server_dir, "worlds")
    os.makedirs(world_dir, exist_ok=True)
    await delete_server_files(server)
    assert not os.path.exists(server.paths.server_dir)

    os.makedirs(server.paths.server_config_dir, exist_ok=True)
    with open(
        os.path.join(server.paths.server_config_dir, "runtime.pid"), "w"
    ) as handle:
        handle.write("0")
    assert server.state.servers.get(server.server_name) is not None

    await delete_all_data(server)
    assert not await aiofiles.ospath.exists(server.paths.server_dir)
    assert not await aiofiles.ospath.exists(server.paths.server_config_dir)
    assert server.state.servers.get(server.server_name) is None
    async with server.storage.transaction() as session:
        record = await server.storage.server_repo.get_server_by_name(
            session, server.server_name
        )
    assert record is None
