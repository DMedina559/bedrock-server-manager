import os

import aiofiles.ospath
import pytest


async def test_is_installed(real_bedrock_server):
    """Test checking if a server is installed."""
    server = real_bedrock_server

    # Fixture creates a dummy executable, so it should be installed
    assert await server.is_installed() is True

    # Remove executable to simulate uninstalled
    os.remove(server.bedrock_executable_path)
    assert await server.is_installed() is False


async def test_validate_installation_success(real_bedrock_server):
    """Test validating a healthy installation."""
    server = real_bedrock_server
    assert await server.validate_installation() is True


async def test_validate_installation_missing_exe(real_bedrock_server):
    """Test validating raises error if executable is missing."""
    server = real_bedrock_server
    os.remove(server.bedrock_executable_path)
    from bedrock_server_manager.error import AppFileNotFoundError

    with pytest.raises(AppFileNotFoundError):
        await server.validate_installation()


async def test_set_filesystem_permissions(real_bedrock_server):
    """Apply filesystem permissions to the actual installation."""
    await real_bedrock_server.set_filesystem_permissions()
    assert os.access(real_bedrock_server.bedrock_executable_path, os.R_OK | os.X_OK)


async def test_delete_server_files(real_bedrock_server):
    """Test deleting all server files."""
    server = real_bedrock_server
    world_dir = os.path.join(server.server_dir, "worlds")
    os.makedirs(world_dir)

    # Note: `keep_worlds` is not an argument for `delete_server_files` in the actual code
    await server.delete_server_files()

    assert not os.path.exists(server.server_dir)


async def test_delete_all_data(real_bedrock_server):
    """Test deleting all server data including configuration."""
    server = real_bedrock_server

    assert os.path.exists(server.server_dir)
    os.makedirs(server.server_config_dir, exist_ok=True)
    with open(os.path.join(server.server_config_dir, "runtime.pid"), "w") as handle:
        handle.write("0")
    assert os.path.exists(server.server_config_dir)

    await server.delete_all_data()

    assert not await aiofiles.ospath.exists(server.server_dir)
    assert not await aiofiles.ospath.exists(server.server_config_dir)
