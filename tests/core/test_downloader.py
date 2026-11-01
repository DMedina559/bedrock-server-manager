"""
Integration tests for bedrock_server_manager/core/downloader.py
"""

import os
import platform
import zipfile
from unittest.mock import patch

import aiohttp
import pytest

from bedrock_server_manager.context import AppContext
from bedrock_server_manager.core.downloader import (
    BedrockDownloader,
    prune_old_downloads,
)
from bedrock_server_manager.error import InternetConnectivityError


async def test_prune_old_downloads(tmp_path):
    """Test prune_old_downloads keeps the specified amount of files and deletes the oldest."""
    downloads_dir = tmp_path / "downloads"
    downloads_dir.mkdir()

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
        time_to_set = 1000000000 + (i * 100)
        os.utime(file_path, (time_to_set, time_to_set))

    await prune_old_downloads(str(downloads_dir), 3)

    remaining_files = os.listdir(downloads_dir)
    assert len(remaining_files) == 3
    assert "bedrock-server-file1.zip" not in remaining_files
    assert "bedrock-server-file2.zip" not in remaining_files
    assert "bedrock-server-file5.zip" in remaining_files


async def test_downloader_init_and_lookup(mock_bedrock_api, app_context: AppContext):
    """Test initialization and looking up LATEST, PREVIEW, and failed URLs."""
    downloader = BedrockDownloader(
        settings_obj=app_context.settings,
        server_dir="/fake/server/dir",
        target_version="LATEST",
    )
    assert downloader.server_dir == os.path.abspath("/fake/server/dir")
    assert downloader.input_target_version == "LATEST"
    assert downloader._version_type == "LATEST"

    preview_downloader = BedrockDownloader(
        settings_obj=app_context.settings,
        server_dir="/fake/server/dir",
        target_version="PREVIEW",
    )
    assert preview_downloader._version_type == "PREVIEW"

    await app_context.settings.set(
        "downloader.download_url", f"{mock_bedrock_api.url}/api/v1.0/download/links"
    )

    latest_url = await downloader._lookup_bedrock_download_url()
    assert mock_bedrock_api.url in latest_url and "bedrock-server" in latest_url

    preview_url = await preview_downloader._lookup_bedrock_download_url()
    assert mock_bedrock_api.url in preview_url and "preview" in preview_url

    with patch(
        "aiohttp.ClientSession.get", side_effect=aiohttp.ClientError("API down")
    ):
        with pytest.raises(
            InternetConnectivityError,
            match="Could not contact the Minecraft download API",
        ):
            await downloader._lookup_bedrock_download_url()


async def test_downloader_prepare_assets_and_full_setup(
    app_context, tmp_path, download_api
):
    await app_context.settings.set("paths.downloads", str(tmp_path / "downloads"))
    downloader = BedrockDownloader(
        app_context.settings, str(tmp_path / "server_prep"), "LATEST"
    )
    version, zip_path, download_dir = await downloader.prepare_download_assets()
    assert version
    assert downloader.resolved_download_url.startswith(download_api.url)
    assert os.path.isfile(zip_path)
    with zipfile.ZipFile(zip_path) as archive:
        assert "server.properties" in archive.namelist()
    assert "stable" in zip_path
    assert os.path.dirname(zip_path) == download_dir

    server_dir = tmp_path / "server_full"
    full_dl = BedrockDownloader(app_context.settings, str(server_dir), "LATEST")
    result_version = await full_dl.full_server_setup(is_update=False)
    assert result_version == full_dl.actual_version
    assert (server_dir / "server.properties").is_file()
    binary = (
        "bedrock_server.exe" if platform.system() == "Windows" else "bedrock_server"
    )
    assert (server_dir / binary).is_file()


async def test_downloader_extract_server_files_fresh_and_update(
    app_context: AppContext, tmp_path, dummy_server_zip
):
    """Test extraction process for both a fresh install and an update preserving properties."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()

    zip_path = dummy_server_zip(target_dir=tmp_path, version="1.20.0.01")

    downloader = BedrockDownloader(app_context.settings, str(server_dir), "LATEST")
    downloader.resolved_download_url = f"https://example.com/{zip_path.name}"
    downloader.actual_version = "1.20.0.01"
    downloader.zip_file_path = str(zip_path)
    downloader.specific_download_dir = str(tmp_path)

    await downloader.extract_server_files(is_update=False)

    if platform.system() == "Windows":
        assert (server_dir / "bedrock_server.exe").exists()
    else:
        assert (server_dir / "bedrock_server").exists()
    assert (server_dir / "server.properties").exists()
    assert (server_dir / "behavior_packs").is_dir()

    # Update preserves custom properties
    existing_props = server_dir / "server.properties"
    existing_props.write_text(
        "server-name=My Custom Server\nold-prop=false\n# some custom comment\nlegacy-prop=123"
    )

    new_zip_path = tmp_path / "modified_server.zip"
    with zipfile.ZipFile(zip_path, "r") as z_in:
        with zipfile.ZipFile(new_zip_path, "w") as z_out:
            for item in z_in.infolist():
                if item.filename != "server.properties":
                    z_out.writestr(item, z_in.read(item.filename))
            z_out.writestr(
                "server.properties",
                "# Server Name Comment\nserver-name=Dedicated Server\nnew-prop=true\nold-prop=true",
            )

    downloader.zip_file_path = str(new_zip_path)
    await downloader.extract_server_files(is_update=True)

    content = existing_props.read_text()
    assert "# Server Name Comment\nserver-name=My Custom Server" in content
    assert "new-prop=true" in content
    assert "old-prop=false" in content
    assert "# Legacy or custom properties" in content
    assert "legacy-prop=123" in content
