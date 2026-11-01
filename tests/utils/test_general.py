import asyncio
import os
from collections import namedtuple

import pytest

from bedrock_server_manager.error import AppFileNotFoundError, FileOperationError
from bedrock_server_manager.utils.general import (
    ReentrantAsyncLock,
    get_timestamp,
    list_content_files,
    startup_checks,
)


async def test_startup_checks_and_dirs(app_context, tmp_path, monkeypatch):
    """Test startup_checks creates missing directories, handles existing ones, and validates Python version."""
    servers_dir = tmp_path / "servers"
    servers_dir.mkdir()  # Existing dir beforehand

    await app_context.settings.set("paths.servers", str(servers_dir))
    await app_context.settings.set("paths.content", str(tmp_path / "content"))
    await app_context.settings.set("paths.downloads", str(tmp_path / "downloads"))
    await app_context.settings.set("paths.plugins", str(tmp_path / "plugins"))
    await app_context.settings.set("paths.backups", str(tmp_path / "backups"))

    startup_checks(app_context)

    assert os.path.isdir(servers_dir)
    assert os.path.isdir(tmp_path / "content")
    assert os.path.isdir(tmp_path / "content" / "worlds")
    assert os.path.isdir(tmp_path / "content" / "addons")
    assert os.path.isdir(tmp_path / "downloads")
    assert os.path.isdir(tmp_path / "plugins")
    assert os.path.isdir(tmp_path / "backups")

    VersionInfo = namedtuple("VersionInfo", ["major", "minor", "micro"])
    monkeypatch.setattr("sys.version_info", VersionInfo(3, 9, 0))
    with pytest.raises(RuntimeError, match="Python version 3.11 or later is required"):
        startup_checks(app_context)


async def test_list_content_files_and_timestamp(tmp_path, monkeypatch):
    """Test get_timestamp and list_content_files across success, empty, missing, and OS error cases."""
    timestamp = get_timestamp()
    assert isinstance(timestamp, str) and len(timestamp) == 15 and timestamp[8] == "_"

    worlds_dir = tmp_path / "worlds"
    worlds_dir.mkdir()
    (worlds_dir / "world1.mcworld").touch()
    (worlds_dir / "world2.mcworld").touch()
    (worlds_dir / "ignore_this.txt").touch()

    result = await list_content_files(str(tmp_path), "worlds", [".mcworld"])
    assert len(result) == 2
    assert any("world1.mcworld" in f for f in result)
    assert any("world2.mcworld" in f for f in result)
    assert not any("ignore_this.txt" in f for f in result)

    # No matches
    addons_dir = tmp_path / "addons"
    addons_dir.mkdir()
    (addons_dir / "file.txt").touch()
    assert await list_content_files(str(tmp_path), "addons", [".mcpack"]) == []

    # Subfolder does not exist
    assert await list_content_files(str(tmp_path), "missing_folder", [".txt"]) == []

    # Content dir missing
    with pytest.raises(AppFileNotFoundError, match="not found at path:"):
        await list_content_files("/does/not/exist/ever", "worlds", [".mcworld"])

    # OS error
    def mock_find_files(*args, **kwargs):
        raise OSError("Permission denied")

    monkeypatch.setattr(
        "bedrock_server_manager.core.system.find_files", mock_find_files
    )
    with pytest.raises(FileOperationError, match="Error scanning content directory"):
        await list_content_files(str(tmp_path), "worlds", [".mcworld"])


def test_reentrant_async_lock_lifecycle():
    """Test ReentrantAsyncLock re-entrancy, cross-event-loop reset, and unacquired release."""
    lock = ReentrantAsyncLock()
    assert not lock.locked()

    async def run_loop_1():
        with pytest.raises(RuntimeError, match="Cannot release un-acquired lock"):
            lock.release()
        async with lock:
            assert lock.locked()
            async with lock:
                assert lock.locked()
                assert lock._count == 2
            assert lock._count == 1
            assert lock.locked()
        assert not lock.locked()
        assert lock._count == 0
        await lock.acquire()
        assert lock.locked()

    asyncio.run(run_loop_1())

    async def run_loop_2():
        await lock.acquire()
        assert lock.locked()
        lock.release()
        assert not lock.locked()

    asyncio.run(run_loop_2())
