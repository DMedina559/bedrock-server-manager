"""
Integration tests for bedrock_server_manager/core/downloader.py
"""

import os
import platform
import zipfile
from unittest.mock import MagicMock, patch

import pytest

from bedrock_server_manager.context import AppContext
from bedrock_server_manager.core.downloader import (
    BedrockDownloader,
    prune_old_downloads,
)
from bedrock_server_manager.error import InternetConnectivityError


def test_prune_old_downloads(tmp_path):
    """Test prune_old_downloads keeps the specified amount of files and deletes the oldest."""
    # Create 5 fake download files with different modification times
    downloads_dir = tmp_path / "downloads"
    downloads_dir.mkdir()

    # Must match the pattern bedrock-server-*.zip
    files = [
        "bedrock-server-file1.zip",
        "bedrock-server-file2.zip",
        "bedrock-server-file3.zip",
        "bedrock-server-file4.zip",
        "bedrock-server-file5.zip",
    ]
    for i, file_name in enumerate(files):
        file_path = downloads_dir / file_name
        file_path.touch()
        # Set explicitly different modification times so sorting is predictable
        # We need to use os.utime to fake mtime
        time_to_set = 1000000000 + (i * 100)  # Ensure increasing time
        os.utime(file_path, (time_to_set, time_to_set))

    # Keep 3, should delete the 2 oldest (file1.zip and file2.zip)
    prune_old_downloads(str(downloads_dir), 3)

    remaining_files = os.listdir(downloads_dir)
    assert len(remaining_files) == 3
    assert "bedrock-server-file1.zip" not in remaining_files
    assert "bedrock-server-file2.zip" not in remaining_files
    assert "bedrock-server-file5.zip" in remaining_files


def test_downloader_init(app_context: AppContext):
    """Test initialization of BedrockDownloader."""
    downloader = BedrockDownloader(
        settings_obj=app_context.settings,
        server_dir="/fake/server/dir",
        target_version="LATEST",
    )

    # Path is absolute internally
    assert downloader.server_dir == os.path.abspath("/fake/server/dir")
    assert downloader.input_target_version == "LATEST"
    assert downloader._version_type == "LATEST"


def test_downloader_init_preview(app_context: AppContext):
    """Test initialization of BedrockDownloader with PREVIEW target."""
    downloader = BedrockDownloader(
        settings_obj=app_context.settings,
        server_dir="/fake/server/dir",
        target_version="PREVIEW",
    )

    assert downloader._version_type == "PREVIEW"


@patch("requests.get")
def test_downloader_lookup_latest(mock_get, app_context: AppContext):
    """Test looking up the latest bedrock URL from API."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    if platform.system() == "Windows":
        mock_response.json.return_value = {
            "result": {
                "links": [
                    {
                        "downloadType": "serverBedrockWindows",
                        "downloadUrl": "https://example.com/bedrock-server-1.20.0.zip",
                    }
                ]
            }
        }
    else:
        mock_response.json.return_value = {
            "result": {
                "links": [
                    {
                        "downloadType": "serverBedrockLinux",
                        "downloadUrl": "https://example.com/bedrock-server-1.20.0.zip",
                    }
                ]
            }
        }
    mock_get.return_value = mock_response

    downloader = BedrockDownloader(app_context.settings, "/fake", "LATEST")
    url = downloader._lookup_bedrock_download_url()

    assert url == "https://example.com/bedrock-server-1.20.0.zip"
    mock_get.assert_called_once()


@patch("requests.get")
def test_downloader_lookup_preview(mock_get, app_context: AppContext):
    """Test looking up the preview bedrock URL from API."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    if platform.system() == "Windows":
        mock_response.json.return_value = {
            "result": {
                "links": [
                    {
                        "downloadType": "serverBedrockPreviewWindows",
                        "downloadUrl": "https://example.com/bedrock-server-1.20.0-preview.zip",
                    }
                ]
            }
        }
    else:
        mock_response.json.return_value = {
            "result": {
                "links": [
                    {
                        "downloadType": "serverBedrockPreviewLinux",
                        "downloadUrl": "https://example.com/bedrock-server-1.20.0-preview.zip",
                    }
                ]
            }
        }
    mock_get.return_value = mock_response

    downloader = BedrockDownloader(app_context.settings, "/fake", "PREVIEW")
    url = downloader._lookup_bedrock_download_url()

    assert url == "https://example.com/bedrock-server-1.20.0-preview.zip"
    mock_get.assert_called_once()


@patch("requests.get")
def test_downloader_lookup_failure(mock_get, app_context: AppContext):
    """Test failing to look up bedrock URL raises InternetConnectivityError."""
    import requests

    mock_get.side_effect = requests.exceptions.RequestException("API down")

    downloader = BedrockDownloader(app_context.settings, "/fake", "LATEST")
    with pytest.raises(
        InternetConnectivityError, match="Could not contact the Minecraft download API"
    ):
        downloader._lookup_bedrock_download_url()


@patch(
    "bedrock_server_manager.core.system.base.check_internet_connectivity",
    return_value=True,
)
def test_downloader_prepare_assets(mock_conn, app_context: AppContext, tmp_path):
    """Test prepare_download_assets sets up paths properly."""
    app_context.settings.set("paths.downloads", str(tmp_path / "downloads"))
    downloader = BedrockDownloader(
        app_context.settings, str(tmp_path / "server_dir"), "LATEST"
    )

    with patch.object(downloader, "get_version_for_target_spec"):
        downloader.actual_version = "1.20.0"
        downloader.resolved_download_url = (
            "https://example.com/bedrock-server-1.20.0.zip"
        )

        with patch.object(downloader, "_download_server_zip_file"):
            with patch.object(downloader, "_execute_instance_pruning"):
                actual_version, zip_path, url = downloader.prepare_download_assets()

                assert url is not None
                assert actual_version == "1.20.0"
                assert "bedrock-server-1.20.0.zip" in zip_path
                assert "stable" in zip_path


def test_downloader_extract_server_files_fresh(app_context: AppContext, tmp_path):
    """Test extraction process for a fresh install."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()

    zip_path = tmp_path / "test.zip"

    # Create a fake zip
    with zipfile.ZipFile(zip_path, "w") as zipf:
        zipf.writestr("bedrock_server", "executable content")
        zipf.writestr("server.properties", "server-name=Dedicated Server")

    downloader = BedrockDownloader(app_context.settings, str(server_dir), "LATEST")
    downloader.resolved_download_url = "https://example.com/test.zip"
    downloader.actual_version = "1.20.0"
    downloader.zip_file_path = str(zip_path)
    downloader.specific_download_dir = str(tmp_path)

    downloader.extract_server_files(is_update=False)

    # Assert extracted
    assert (server_dir / "bedrock_server").exists()
    assert (server_dir / "server.properties").exists()


def test_downloader_extract_server_files_update(app_context: AppContext, tmp_path):
    """Test extraction process for an update preserves properties."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()

    # Create existing server properties
    existing_props = server_dir / "server.properties"
    existing_props.write_text("server-name=My Custom Server")

    zip_path = tmp_path / "test.zip"

    # Create a fake zip with default properties
    with zipfile.ZipFile(zip_path, "w") as zipf:
        zipf.writestr("bedrock_server", "executable content")
        zipf.writestr(
            "server.properties", "server-name=Dedicated Server\nnew-prop=true"
        )

    downloader = BedrockDownloader(app_context.settings, str(server_dir), "LATEST")
    downloader.resolved_download_url = "https://example.com/test.zip"
    downloader.actual_version = "1.20.0"
    downloader.zip_file_path = str(zip_path)
    downloader.specific_download_dir = str(tmp_path)

    downloader.extract_server_files(is_update=True)

    # Assert properties were updated but preserved custom value
    content = existing_props.read_text()
    assert "server-name=My Custom Server" in content
    assert "new-prop=true" in content


@patch(
    "bedrock_server_manager.core.downloader.BedrockDownloader.prepare_download_assets"
)
@patch("bedrock_server_manager.core.downloader.BedrockDownloader.extract_server_files")
def test_full_server_setup(mock_extract, mock_prepare, app_context: AppContext):
    """Test full setup orchestration."""
    mock_prepare.return_value = ("1.20.0", "/fake/zip.zip", "https://url")

    downloader = BedrockDownloader(app_context.settings, "/fake", "LATEST")
    result_version = downloader.full_server_setup(is_update=False)

    assert result_version == "1.20.0"
    mock_prepare.assert_called_once()
    mock_extract.assert_called_once_with(False)
