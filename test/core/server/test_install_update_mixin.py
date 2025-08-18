import pytest
import os
import shutil
import zipfile
import tempfile
from unittest.mock import patch, MagicMock

from bedrock_server_manager.core.server.install_update_mixin import (
    ServerInstallUpdateMixin,
)
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.core.server.config_management_mixin import (
    ServerConfigManagementMixin,
)
from bedrock_server_manager.core.server.world_mixin import ServerWorldMixin
from bedrock_server_manager.config.settings import Settings
from bedrock_server_manager.core.downloader import BedrockDownloader
from bedrock_server_manager.core.server.state_mixin import ServerStateMixin
from bedrock_server_manager.core.server.installation_mixin import (
    ServerInstallationMixin,
)
from bedrock_server_manager.core.server.process_mixin import ServerProcessMixin
from bedrock_server_manager.error import (
    ServerStopError,
    DownloadError,
    ExtractError,
    PermissionsError,
)


@patch("bedrock_server_manager.core.server.install_update_mixin.BedrockDownloader")
@patch(
    "bedrock_server_manager.core.server.install_update_mixin.ServerInstallUpdateMixin._perform_server_files_setup"
)
def test_install_or_update_install(mock_setup, mock_downloader, app_context):
    server = app_context.get_server("test_server")
    mock_downloader_instance = mock_downloader.return_value
    mock_downloader_instance.prepare_download_assets.return_value = (
        "1.20.0",
        "/path/to/zip",
        "/path/to/downloads",
    )

    with patch.object(server, "is_installed", return_value=False):
        server.install_or_update("LATEST")

    mock_downloader.assert_called_with(
        settings_obj=server.settings,
        server_dir=server.server_dir,
        target_version="LATEST",
        server_zip_path=None,
    )
    mock_downloader_instance.prepare_download_assets.assert_called_once()
    mock_setup.assert_called_with(mock_downloader_instance, False)


@patch("bedrock_server_manager.core.server.install_update_mixin.BedrockDownloader")
@patch(
    "bedrock_server_manager.core.server.install_update_mixin.ServerInstallUpdateMixin._perform_server_files_setup"
)
@patch(
    "bedrock_server_manager.core.server.install_update_mixin.ServerInstallUpdateMixin.is_update_needed",
    return_value=True,
)
def test_install_or_update_update(
    mock_is_update_needed, mock_setup, mock_downloader, app_context
):
    server = app_context.get_server("test_server")
    mock_downloader_instance = mock_downloader.return_value
    mock_downloader_instance.prepare_download_assets.return_value = (
        "1.20.0",
        "/path/to/zip",
        "/path/to/downloads",
    )

    with patch.object(server, "is_installed", return_value=True):
        server.install_or_update("LATEST")

    mock_is_update_needed.assert_called_with("LATEST")
    mock_downloader.assert_called_with(
        settings_obj=server.settings,
        server_dir=server.server_dir,
        target_version="LATEST",
        server_zip_path=None,
    )
    mock_downloader_instance.prepare_download_assets.assert_called_once()
    mock_setup.assert_called_with(mock_downloader_instance, True)


@patch("bedrock_server_manager.core.server.install_update_mixin.BedrockDownloader")
def test_is_update_needed_specific_version(mock_downloader, app_context):
    server = app_context.get_server("test_server")
    mock_downloader.return_value._custom_version_number = "1.20.0"
    with patch.object(server, "get_version", return_value="1.19.0"):
        assert server.is_update_needed("1.20.0") is True
    mock_downloader.return_value._custom_version_number = "1.19.0"
    with patch.object(server, "get_version", return_value="1.19.0"):
        assert server.is_update_needed("1.19.0") is False


@patch("bedrock_server_manager.core.server.install_update_mixin.BedrockDownloader")
def test_is_update_needed_latest(mock_downloader, app_context):
    server = app_context.get_server("test_server")
    mock_downloader.return_value.get_version_for_target_spec.return_value = "1.20.0"
    with patch.object(server, "get_version", return_value="1.19.0"):
        assert server.is_update_needed("LATEST") is True
    with patch.object(server, "get_version", return_value="1.20.0"):
        assert server.is_update_needed("LATEST") is False


@patch("bedrock_server_manager.core.server.install_update_mixin.BedrockDownloader")
def test_is_update_needed_preview(mock_downloader, app_context):
    server = app_context.get_server("test_server")
    mock_downloader.return_value.get_version_for_target_spec.return_value = (
        "1.20.0-preview"
    )
    with patch.object(server, "get_version", return_value="1.19.0"):
        assert server.is_update_needed("PREVIEW") is True
    with patch.object(server, "get_version", return_value="1.20.0-preview"):
        assert server.is_update_needed("PREVIEW") is False


def test_install_or_update_server_stop_error(app_context):
    server = app_context.get_server("test_server")
    with patch.object(server, "is_running", return_value=True):
        with patch.object(server, "stop", side_effect=ServerStopError):
            with pytest.raises(ServerStopError):
                server.install_or_update("LATEST")


@patch(
    "bedrock_server_manager.core.server.install_update_mixin.BedrockDownloader.prepare_download_assets",
    side_effect=DownloadError,
)
def test_install_or_update_download_error(mock_prepare, app_context):
    server = app_context.get_server("test_server")
    with pytest.raises(DownloadError):
        server.install_or_update("LATEST")


@patch(
    "bedrock_server_manager.core.server.install_update_mixin.BedrockDownloader.prepare_download_assets"
)
@patch(
    "bedrock_server_manager.core.server.install_update_mixin.ServerInstallUpdateMixin._perform_server_files_setup",
    side_effect=ExtractError,
)
def test_install_or_update_extract_error(mock_setup, mock_prepare, app_context):
    server = app_context.get_server("test_server")
    mock_prepare.return_value = ("1.20.0", "/path/to/zip", "/path/to/downloads")
    with pytest.raises(ExtractError):
        server.install_or_update("LATEST")


@patch(
    "bedrock_server_manager.core.server.install_update_mixin.BedrockDownloader.prepare_download_assets"
)
@patch(
    "bedrock_server_manager.core.server.install_update_mixin.ServerInstallUpdateMixin._perform_server_files_setup",
    side_effect=PermissionsError,
)
def test_install_or_update_permissions_error(mock_setup, mock_prepare, app_context):
    server = app_context.get_server("test_server")
    mock_prepare.return_value = ("1.20.0", "/path/to/zip", "/path/to/downloads")
    with pytest.raises(PermissionsError):
        server.install_or_update("LATEST")


@patch("bedrock_server_manager.core.downloader.BedrockDownloader.extract_server_files")
def test_perform_server_files_setup_permissions_error(mock_extract, app_context):
    server = app_context.get_server("test_server")
    downloader = BedrockDownloader(server.settings, server.server_dir, "LATEST")
    with patch.object(downloader, "get_zip_file_path", return_value="/path/to/zip"):
        with patch.object(
            server, "set_filesystem_permissions", side_effect=PermissionsError
        ):
            with pytest.raises(PermissionsError):
                server._perform_server_files_setup(downloader, False)
