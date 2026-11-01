"""Tests for the base system utilities in bedrock_server_manager.core.system.base."""

import asyncio
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import psutil
import pytest

from bedrock_server_manager.core.system.base import (
    ProcessResourceMonitor,
    can_manage_services,
    check_internet_connectivity,
    delete_path_robustly,
    find_files,
    is_server_running,
    set_server_folder_permissions,
)
from bedrock_server_manager.error import (
    AppFileNotFoundError,
    InternetConnectivityError,
    MissingArgumentError,
    PermissionsError,
)


async def test_find_files(tmp_path: Path):
    """Test finding files and getting their metadata."""
    dir_path = tmp_path / "find_files_dir"
    dir_path.mkdir()

    file1 = dir_path / "a.txt"
    file1.write_text("hello")
    file2 = dir_path / "b.txt"
    file2.write_text("world!")

    # Test path returned
    files = await find_files(str(dir_path), pattern="*.txt")
    assert len(files) == 2
    assert str(file1) in files
    assert str(file2) in files

    # Test metadata
    metadata = cast(
        list[dict[str, Any]],
        await find_files(str(dir_path), pattern="*.txt", include_metadata=True),
    )
    assert len(metadata) == 2
    # Find specific files in metadata
    meta1 = next(m for m in metadata if m["name"] == "a.txt")
    assert meta1["size"] == 5
    meta2 = next(m for m in metadata if m["name"] == "b.txt")
    assert meta2["size"] == 6


def test_can_manage_services():
    """Test checking if user can manage services."""
    # This is a bit OS dependent. On linux, it depends on whether systemctl is available
    # and if the user is root or has systemctl. We can just ensure it doesn't crash and returns a bool.
    assert isinstance(can_manage_services(), bool)


async def test_check_internet_connectivity(mock_http_server):
    """Check connectivity through a local HTTP endpoint and error branches."""
    await check_internet_connectivity(url=mock_http_server.url)
    for err in (TimeoutError, aiohttp.ClientError):
        with patch("aiohttp.ClientSession.get", side_effect=err):
            with pytest.raises(InternetConnectivityError):
                await check_internet_connectivity()


async def test_set_server_folder_permissions_linux(tmp_path: Path):
    """Test setting server folder permissions on Linux."""
    if os.name != "posix":
        pytest.skip("Linux specific test")

    server_dir = tmp_path / "linux_server"
    server_dir.mkdir()

    executable = server_dir / "bedrock_server"
    executable.write_text("exe")
    text_file = server_dir / "test.txt"
    text_file.write_text("text")
    sub_dir = server_dir / "a_dir"
    sub_dir.mkdir()

    await set_server_folder_permissions(str(server_dir))

    assert stat.S_IMODE(server_dir.stat().st_mode) == 0o775
    assert stat.S_IMODE(executable.stat().st_mode) == 0o775
    assert stat.S_IMODE(text_file.stat().st_mode) == 0o664
    assert stat.S_IMODE(sub_dir.stat().st_mode) == 0o775


async def test_set_server_folder_permissions_windows(tmp_path: Path):
    """Test setting server folder permissions on Windows."""
    if os.name != "nt":
        pytest.skip("Windows specific test")

    server_dir = tmp_path / "win_server"
    server_dir.mkdir()
    test_file = server_dir / "test.txt"
    test_file.write_text("test")

    # Make file read-only
    os.chmod(test_file, stat.S_IREAD)

    await set_server_folder_permissions(str(server_dir))

    assert os.access(str(test_file), os.W_OK)


async def test_set_server_folder_permissions_non_existent():
    """Test setting permissions on a directory that doesn't exist."""
    with pytest.raises(AppFileNotFoundError):
        await set_server_folder_permissions("does_not_exist_dir")


@pytest.mark.skipif(os.name != "posix", reason="Linux specific test")
@patch("os.chmod", side_effect=OSError)
async def test_set_server_folder_permissions_os_error_on_chmod(
    mock_chmod, tmp_path: Path
):
    """Test handling of OSError during chmod on Linux."""
    server_dir = tmp_path / "err_server"
    server_dir.mkdir()
    with pytest.raises(PermissionsError):
        await set_server_folder_permissions(str(server_dir))


@pytest.mark.skipif(os.name != "posix", reason="Linux specific test")
@patch("os.chown", side_effect=OSError)
async def test_set_server_folder_permissions_os_error_on_chown(
    mock_chown, tmp_path: Path
):
    """Test handling of OSError during chown on Linux."""
    server_dir = tmp_path / "err_server_chown"
    server_dir.mkdir()
    with pytest.raises(PermissionsError):
        await set_server_folder_permissions(str(server_dir))


async def test_delete_path_robustly_scenarios(tmp_path: Path):
    """Test deleting files, read-only files, directories, non-existent paths, and invalid inputs."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("test")
    assert await delete_path_robustly(str(file_path), "test file") is True
    assert not file_path.exists()

    ro_file = tmp_path / "readonly.txt"
    ro_file.write_text("readonly")
    os.chmod(ro_file, stat.S_IREAD)
    assert await delete_path_robustly(str(ro_file), "readonly test file") is True
    assert not ro_file.exists()

    dir_path = tmp_path / "test_dir"
    dir_path.mkdir()
    assert await delete_path_robustly(str(dir_path), "test directory") is True
    assert not dir_path.exists()

    ro_dir = tmp_path / "readonly_dir"
    ro_dir.mkdir()
    ro_child = ro_dir / "readonly.txt"
    ro_child.write_text("readonly")
    os.chmod(ro_child, stat.S_IREAD)
    assert (
        await delete_path_robustly(str(ro_dir), "directory with read-only file") is True
    )
    assert not ro_dir.exists()

    non_existent = tmp_path / "non_existent"
    assert await delete_path_robustly(str(non_existent), "non existent path") is True

    with pytest.raises(MissingArgumentError):
        await delete_path_robustly("", "description")
    with pytest.raises(MissingArgumentError):
        await delete_path_robustly("path", "")
    with pytest.raises(MissingArgumentError):
        await delete_path_robustly(None, "description")  # type: ignore


async def test_is_server_running_checks():
    """Test await is_server_running when process is found or not found."""
    with patch(
        "bedrock_server_manager.core.system.base.core_process.get_verified_bedrock_process",
        new_callable=AsyncMock,
    ) as mock_get:
        mock_get.return_value = MagicMock()
        assert (
            await is_server_running("server", "/path/to/server", "/path/to/config")
            is True
        )
        mock_get.return_value = None
        assert (
            await is_server_running("server", "/path/to/server", "/path/to/config")
            is False
        )


async def test_resource_monitor_real_and_edge_cases():
    """Test ProcessResourceMonitor with a real short-lived process and edge cases."""
    monitor = ProcessResourceMonitor()

    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(2)"])
    try:
        await asyncio.sleep(0.05)
        ps_proc = psutil.Process(process.pid)

        stats = monitor.get_stats(ps_proc)
        assert stats is not None
        assert isinstance(stats["cpu_percent"], float)
        assert isinstance(stats["memory_mb"], float)
        assert stats["pid"] == process.pid

        await asyncio.sleep(0.1)
        stats2 = monitor.get_stats(ps_proc)
        assert stats2 is not None
        assert isinstance(stats2["cpu_percent"], float)
    finally:
        process.terminate()
        process.wait()

    with patch("bedrock_server_manager.core.system.base.PSUTIL_AVAILABLE", False):
        assert ProcessResourceMonitor().get_stats(MagicMock()) is None

    with pytest.raises(TypeError):
        monitor.get_stats("not a process")  # type: ignore

    mock_proc = MagicMock()
    mock_proc.pid = 99999999
    mock_proc.cpu_percent.side_effect = psutil.NoSuchProcess(mock_proc.pid)
    assert monitor.get_stats(mock_proc) is None


async def test_windows_permission_failures_propagate(real_bedrock_server, monkeypatch):
    from bedrock_server_manager.core.system import base
    from bedrock_server_manager.error import PermissionsError

    def failed(*args, **kwargs):
        raise PermissionError("write permission refused")

    with monkeypatch.context() as fault:
        fault.setattr(base.platform, "system", lambda: "Windows")
        fault.setattr(base.os, "chmod", failed)
        with pytest.raises(PermissionsError):
            await base.set_server_folder_permissions(
                real_bedrock_server.paths.server_dir
            )
