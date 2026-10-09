import os

import aiofiles.ospath
import pytest

from bedrock_server_manager.core.server.removal import (
    delete_all_data,
    delete_server_files,
    set_filesystem_permissions,
)


async def test_is_installed(real_bedrock_server):
    """Test checking if a server is installed."""
    server = real_bedrock_server

    # Fixture creates a dummy executable, so it should be installed
    assert await server.is_installed() is True

    # Remove executable to simulate uninstalled
    os.remove(server.paths.bedrock_executable_path)
    assert await server.is_installed() is False


async def test_validate_installation_success(real_bedrock_server):
    """Test validating a healthy installation."""
    server = real_bedrock_server
    assert await server.validate_installation() is True


async def test_validate_installation_missing_exe(real_bedrock_server):
    """Test validating raises error if executable is missing."""
    server = real_bedrock_server
    os.remove(server.paths.bedrock_executable_path)
    from bedrock_server_manager.error import AppFileNotFoundError

    with pytest.raises(AppFileNotFoundError):
        await server.validate_installation()


async def test_set_filesystem_permissions(real_bedrock_server):
    """Apply filesystem permissions to the actual installation."""
    await set_filesystem_permissions(real_bedrock_server)
    assert os.access(
        real_bedrock_server.paths.bedrock_executable_path, os.R_OK | os.X_OK
    )


async def test_delete_server_files(real_bedrock_server):
    """Test deleting all server files."""
    server = real_bedrock_server
    world_dir = os.path.join(server.paths.server_dir, "worlds")
    os.makedirs(world_dir)

    # Note: `keep_worlds` is not an argument for `delete_server_files` in the actual code
    await delete_server_files(server)

    assert not os.path.exists(server.paths.server_dir)


async def test_delete_all_data(real_bedrock_server):
    """Test deleting all server data including configuration."""
    server = real_bedrock_server

    assert os.path.exists(server.paths.server_dir)
    os.makedirs(server.paths.server_config_dir, exist_ok=True)
    with open(
        os.path.join(server.paths.server_config_dir, "runtime.pid"), "w"
    ) as handle:
        handle.write("0")
    assert os.path.exists(server.paths.server_config_dir)

    await delete_all_data(server)

    assert not await aiofiles.ospath.exists(server.paths.server_dir)
    assert not await aiofiles.ospath.exists(server.paths.server_config_dir)


async def test_delete_record_without_installation_or_backups(real_bedrock_server):
    """Deletion also removes configuration and persistence after files disappear."""
    server = real_bedrock_server
    await delete_server_files(server)
    os.makedirs(server.paths.server_config_dir, exist_ok=True)
    assert server.state.servers.get(server.server_name) is not None

    await delete_all_data(server)

    assert not os.path.exists(server.paths.server_config_dir)
    assert server.state.servers.get(server.server_name) is None
    async with server.storage.transaction() as session:
        record = await server.storage.server_repo.get_server_by_name(
            session, server.server_name
        )
    assert record is None
