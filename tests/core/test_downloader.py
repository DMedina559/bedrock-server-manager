import asyncio
import threading

"""
Integration tests for bedrock_server_manager/core/downloader.py
"""

import os
import platform
import zipfile

import pytest
from bsm_test_utils import RouteBehavior

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


async def test_downloader_init_and_lookup(
    bedrock_download_catalog, app_context: AppContext
):
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

    server = bedrock_download_catalog.publish()
    links_path = "/api/v1.0/download/links"
    await app_context.settings.set("downloader.download_url", server.url + links_path)

    latest_url = await downloader._lookup_bedrock_download_url()
    assert server.url in latest_url and "bedrock-server" in latest_url

    preview_url = await preview_downloader._lookup_bedrock_download_url()
    assert server.url in preview_url and "preview" in preview_url

    bedrock_download_catalog.publish(stable="1.26.46.1")
    updated_url = await downloader._lookup_bedrock_download_url()
    assert updated_url.endswith("/bedrock-server-1.26.46.1.zip")
    assert updated_url != latest_url

    server.add_route(links_path, RouteBehavior(status_code=503))
    with pytest.raises(
        InternetConnectivityError, match="Could not contact the Minecraft download API"
    ):
        await downloader._lookup_bedrock_download_url()
    assert [request.path for request in server.requests] == [links_path] * 4


async def test_downloader_prepare_assets_and_full_setup(
    app_context, tmp_path, download_api, bedrock_download_catalog
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

    properties = server_dir / "server.properties"
    custom_name = "server-name=Keep existing settings"
    properties.write_text(custom_name + "\n", encoding="utf-8")
    bedrock_download_catalog.publish(stable="1.26.46.1")
    update = BedrockDownloader(app_context.settings, str(server_dir), "LATEST")
    assert await update.full_server_setup(is_update=True) == "1.26.46.1"
    names = [
        line
        for line in properties.read_text(encoding="utf-8").splitlines()
        if line.startswith("server-name=")
    ]
    assert names == [custom_name]


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


async def test_cancel_install_rolls_back_files_before_returning(
    app_context, tmp_path, dummy_server_zip, monkeypatch
):
    from bedrock_server_manager.core.files import FileTransaction

    target = tmp_path / "cancel-install"
    target.mkdir()
    (target / "server.properties").write_text("old properties")
    binary = (
        "bedrock_server.exe" if platform.system() == "Windows" else "bedrock_server"
    )
    (target / binary).write_bytes(b"old executable")
    original_files = {p.name: p.read_bytes() for p in target.iterdir()}
    archive = dummy_server_zip(target_dir=tmp_path, version="1.26.45.1")
    downloader = BedrockDownloader(app_context.settings, str(target), "LATEST")
    downloader.zip_file_path = str(archive)
    replace = FileTransaction.replace
    replaced = asyncio.Event()
    drain = threading.Event()
    loop = asyncio.get_running_loop()

    def pause_after_first_replace(self, source, destination):
        replace(self, source, destination)
        loop.call_soon_threadsafe(replaced.set)
        assert drain.wait(5)

    monkeypatch.setattr(FileTransaction, "replace", pause_after_first_replace)
    task = asyncio.create_task(downloader.extract_server_files(is_update=False))
    try:
        await asyncio.wait_for(replaced.wait(), 5)
        task.cancel()
    finally:
        drain.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert {p.name: p.read_bytes() for p in target.iterdir()} == original_files
    assert not list(tmp_path.glob("bsm-rollback-*"))
