import os
from unittest.mock import patch

import pytest


def test_is_installed(real_bedrock_server):
    """Test checking if a server is installed."""
    server = real_bedrock_server

    # Fixture creates a dummy executable, so it should be installed
    assert server.is_installed() is True

    # Remove executable to simulate uninstalled
    os.remove(server.bedrock_executable_path)
    assert server.is_installed() is False


def test_validate_installation_success(real_bedrock_server):
    """Test validating a healthy installation."""
    server = real_bedrock_server
    assert server.validate_installation() is True


def test_validate_installation_missing_exe(real_bedrock_server):
    """Test validating raises error if executable is missing."""
    server = real_bedrock_server
    os.remove(server.bedrock_executable_path)
    from bedrock_server_manager.error import AppFileNotFoundError

    with pytest.raises(AppFileNotFoundError):
        server.validate_installation()


def test_set_filesystem_permissions(real_bedrock_server):
    """Test setting filesystem permissions delegates to system_base."""
    server = real_bedrock_server
    with patch(
        "bedrock_server_manager.core.server.installation_mixin.system_base.set_server_folder_permissions"
    ) as mock_set_perms:
        server.set_filesystem_permissions()
        mock_set_perms.assert_called_once_with(server.server_dir)


def test_delete_server_files(real_bedrock_server):
    """Test deleting all server files."""
    server = real_bedrock_server
    world_dir = os.path.join(server.server_dir, "worlds")
    os.makedirs(world_dir)

    # Note: `keep_worlds` is not an argument for `delete_server_files` in the actual code
    server.delete_server_files()

    assert not os.path.exists(server.server_dir)


def test_delete_all_data(real_bedrock_server):
    """Test deleting all server data including configuration."""
    server = real_bedrock_server

    assert os.path.exists(server.server_dir)
    assert os.path.exists(server.server_config_dir)

    server.delete_all_data()

    assert not os.path.exists(server.server_dir)
    assert not os.path.exists(server.server_config_dir)
