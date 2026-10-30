import os
import stat
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from bedrock_server_manager.core.downloader import BedrockDownloader
from bedrock_server_manager.core.files import extract_archive, file_transaction
from bedrock_server_manager.core.manifests import PackManifest
from bedrock_server_manager.error import FileOperationError


@pytest.mark.parametrize(
    "name",
    ["../outside", "/outside", "C:/outside", "folder/../../outside", "..\\outside"],
)
def test_archive_rejects_unsafe_names_before_any_write(tmp_path, name):
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("safe.txt", "safe")
        archive.writestr(name, "unsafe")
    target = tmp_path / "target"
    with zipfile.ZipFile(archive_path) as archive, pytest.raises(zipfile.BadZipFile):
        extract_archive(archive, target)
    assert not target.exists()


def test_archive_rejects_symlinks(tmp_path):
    path = tmp_path / "link.zip"
    entry = zipfile.ZipInfo("link")
    entry.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(entry, "outside")
    with zipfile.ZipFile(path) as archive, pytest.raises(zipfile.BadZipFile):
        extract_archive(archive, tmp_path / "target")


@pytest.mark.asyncio
async def test_replacement_rolls_back_all_files_and_activation(tmp_path):
    live = tmp_path / "live"
    live.mkdir()
    original = live / "old.txt"
    original.write_text("old")
    activation = live / "activation.json"
    activation.write_text("[]")
    source = tmp_path / "new.txt"
    source.write_text("new")
    with pytest.raises(RuntimeError, match="activation failed"):
        async with file_transaction(tmp_path) as transaction:
            transaction.retire(original)
            transaction.replace(source, live / "new.txt")
            transaction.watch(activation)
            activation.write_text("invalid")
            raise RuntimeError("activation failed")
    assert original.read_text() == "old"
    assert activation.read_text() == "[]"
    assert not (live / "new.txt").exists()
    assert not list(tmp_path.glob("bsm-rollback-*"))


@pytest.mark.asyncio
async def test_failed_rename_restores_previous_directory(tmp_path, monkeypatch):
    old = tmp_path / "live"
    old.mkdir()
    (old / "marker").write_text("old")
    source = tmp_path / "source"
    source.mkdir()
    replace = os.replace

    def fail_new(src, dst):
        if Path(src) == source:
            raise OSError("disk error")
        replace(src, dst)

    monkeypatch.setattr(os, "replace", fail_new)
    with pytest.raises(OSError, match="disk error"):
        async with file_transaction(tmp_path) as transaction:
            transaction.replace(source, old)
    assert (old / "marker").read_text() == "old"


def test_manifest_normalizes_legacy_metadata():
    manifest = PackManifest.model_validate(
        {
            "header": {"uuid": "legacy", "version": "1.2"},
            "modules": [{"description": "Behavior pack"}],
            "custom": {"supported": True},
        }
    )
    assert manifest.header.version == [1, 2, 0]
    assert manifest.header.name == "Unknown Subpack Container"
    assert manifest.pack_type == "data"
    assert manifest.model_dump()["custom"] == {"supported": True}


@pytest.mark.asyncio
async def test_addon_activation_failure_restores_old_pack(
    real_bedrock_server, tmp_path, monkeypatch
):
    server = real_bedrock_server
    world = Path(server.paths.server_dir) / "worlds" / await server.get_world_name()
    old = world / "behavior_packs" / "Old_1.0.0"
    old.mkdir(parents=True)
    (old / "marker").write_text("old content")
    source = tmp_path / "pack"
    source.mkdir()
    (source / "manifest.json").write_text(
        '{"header":{"uuid":"same","version":[2,0,0],"name":"New"},"modules":[{"type":"data"}]}'
    )
    activation = world / "world_behavior_packs.json"
    activation.write_text("[]")
    monkeypatch.setattr(
        server.addons,
        "_scan_physical_packs",
        AsyncMock(return_value=[{"uuid": "same", "path": str(old)}]),
    )
    monkeypatch.setattr(
        server.addons,
        "_update_world_pack_json_file",
        AsyncMock(side_effect=FileOperationError("activation failed")),
    )
    with pytest.raises(FileOperationError):
        await server.addons._install_pack_from_extracted_data(str(source), "new.mcpack")
    assert (old / "marker").read_text() == "old content"
    assert activation.read_text() == "[]"
    assert not (world / "behavior_packs" / "New_2.0.0").exists()


@pytest.mark.asyncio
async def test_server_update_failure_rolls_back_previous_files(
    app_context, tmp_path, monkeypatch
):
    server = tmp_path / "server"
    server.mkdir()
    (server / "a").write_text("old a")
    (server / "b").write_text("old b")
    path = tmp_path / "update.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("a", "new a")
        archive.writestr("b", "new b")
    downloader = BedrockDownloader(app_context.settings, str(server), "LATEST")
    downloader.zip_file_path = str(path)
    replace = os.replace

    def fail_second(src, dst):
        if Path(src).name == "b" and Path(dst) == server / "b":
            raise OSError("disk error")
        replace(src, dst)

    monkeypatch.setattr(os, "replace", fail_second)
    with pytest.raises(FileOperationError):
        await downloader.extract_server_files(True)
    assert (server / "a").read_text() == "old a"
    assert (server / "b").read_text() == "old b"
    assert not list(tmp_path.glob("bsm-*"))


@pytest.mark.asyncio
async def test_download_failure_preserves_existing_cache(
    app_context, tmp_path, monkeypatch
):
    import aiohttp

    destination = tmp_path / "cached.zip"
    destination.write_bytes(b"previous download")
    downloader = BedrockDownloader(
        app_context.settings, str(tmp_path / "server"), "LATEST"
    )
    downloader.resolved_download_url = "https://example.com/server.zip"
    downloader.zip_file_path = str(destination)

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def get(self, url):
            raise aiohttp.ClientError("connection lost")

    monkeypatch.setattr(aiohttp, "ClientSession", lambda **kwargs: Session())
    from bedrock_server_manager.error import InternetConnectivityError

    with pytest.raises(InternetConnectivityError):
        await downloader._download_server_zip_file()
    assert destination.read_bytes() == b"previous download"
    assert not list(tmp_path.glob("bsm-*"))


def test_world_export_failure_preserves_existing_archive(tmp_path, monkeypatch):
    import shutil

    from bedrock_server_manager.core.files import atomic_world_archive

    source = tmp_path / "world"
    source.mkdir()
    target = tmp_path / "backup.mcworld"
    target.write_bytes(b"previous backup")

    def fail_archive(base_name, **kwargs):
        Path(base_name + ".zip").write_bytes(b"partial")
        raise OSError("archive failed")

    monkeypatch.setattr(shutil, "make_archive", fail_archive)
    with pytest.raises(OSError, match="archive failed"):
        atomic_world_archive(str(source), str(target))
    assert target.read_bytes() == b"previous backup"
    assert not list(tmp_path.glob("bsm-export-*"))


@pytest.mark.asyncio
async def test_invalid_world_archive_preserves_existing_world(
    real_bedrock_server, tmp_path
):
    from bedrock_server_manager.error import ExtractError

    server = real_bedrock_server
    world = Path(server.worlds._worlds_base_dir_in_server) / "active"
    world.mkdir(parents=True, exist_ok=True)
    marker = world / "level.dat"
    marker.write_bytes(b"previous world data")
    archive = tmp_path / "broken.mcworld"
    archive.write_bytes(b"not a zip")
    with pytest.raises(ExtractError):
        await server.worlds.extract_mcworld(str(archive), "active")
    assert marker.read_bytes() == b"previous world data"
