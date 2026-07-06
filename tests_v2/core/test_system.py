"""Tests for the base system utilities in bedrock_server_manager.core.system.base."""

import os
import stat
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import psutil
import pytest

from bedrock_server_manager.core.system.base import (
    ResourceMonitor,
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


def test_find_files(tmp_path: Path):
    """Test finding files and getting their metadata."""
    dir_path = tmp_path / "find_files_dir"
    dir_path.mkdir()

    file1 = dir_path / "a.txt"
    file1.write_text("hello")
    file2 = dir_path / "b.txt"
    file2.write_text("world!")

    # Test path returned
    files = find_files(str(dir_path), pattern="*.txt")
    assert len(files) == 2
    assert str(file1) in files
    assert str(file2) in files

    # Test metadata
    metadata = find_files(str(dir_path), pattern="*.txt", include_metadata=True)
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


def test_check_internet_connectivity_success():
    """Test checking internet connectivity when it succeeds."""
    # Assuming the sandbox has internet access.
    # Otherwise we can mock socket.create_connection.
    check_internet_connectivity()


@patch("socket.create_connection", side_effect=TimeoutError)
def test_check_internet_connectivity_timeout(mock_socket):
    """Test checking internet connectivity handling a timeout."""
    with pytest.raises(InternetConnectivityError):
        check_internet_connectivity()


@patch("socket.create_connection", side_effect=OSError)
def test_check_internet_connectivity_os_error(mock_socket):
    """Test checking internet connectivity handling an OS Error."""
    with pytest.raises(InternetConnectivityError):
        check_internet_connectivity()


def test_set_server_folder_permissions_linux(tmp_path: Path):
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

    set_server_folder_permissions(str(server_dir))

    assert stat.S_IMODE(server_dir.stat().st_mode) == 0o775
    assert stat.S_IMODE(executable.stat().st_mode) == 0o775
    assert stat.S_IMODE(text_file.stat().st_mode) == 0o664
    assert stat.S_IMODE(sub_dir.stat().st_mode) == 0o775


def test_set_server_folder_permissions_windows(tmp_path: Path):
    """Test setting server folder permissions on Windows."""
    if os.name != "nt":
        pytest.skip("Windows specific test")

    server_dir = tmp_path / "win_server"
    server_dir.mkdir()
    test_file = server_dir / "test.txt"
    test_file.write_text("test")

    # Make file read-only
    os.chmod(test_file, stat.S_IREAD)

    set_server_folder_permissions(str(server_dir))

    assert os.access(str(test_file), os.W_OK)


def test_set_server_folder_permissions_non_existent():
    """Test setting permissions on a directory that doesn't exist."""
    with pytest.raises(AppFileNotFoundError):
        set_server_folder_permissions("does_not_exist_dir")


@pytest.mark.skipif(os.name != "posix", reason="Linux specific test")
@patch("os.chmod", side_effect=OSError)
def test_set_server_folder_permissions_os_error_on_chmod(mock_chmod, tmp_path: Path):
    """Test handling of OSError during chmod on Linux."""
    server_dir = tmp_path / "err_server"
    server_dir.mkdir()
    with pytest.raises(PermissionsError):
        set_server_folder_permissions(str(server_dir))


@pytest.mark.skipif(os.name != "posix", reason="Linux specific test")
@patch("os.chown", side_effect=OSError)
def test_set_server_folder_permissions_os_error_on_chown(mock_chown, tmp_path: Path):
    """Test handling of OSError during chown on Linux."""
    server_dir = tmp_path / "err_server_chown"
    server_dir.mkdir()
    with pytest.raises(PermissionsError):
        set_server_folder_permissions(str(server_dir))


def test_delete_path_robustly_file(tmp_path: Path):
    """Test deleting a normal file."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("test")
    assert file_path.exists()
    assert delete_path_robustly(str(file_path), "test file") is True
    assert not file_path.exists()


def test_delete_path_robustly_readonly_file(tmp_path: Path):
    """Test deleting a read-only file."""
    file_path = tmp_path / "readonly.txt"
    file_path.write_text("readonly")
    os.chmod(file_path, stat.S_IREAD)
    assert file_path.exists()
    assert delete_path_robustly(str(file_path), "readonly test file") is True
    assert not file_path.exists()


def test_delete_path_robustly_dir(tmp_path: Path):
    """Test deleting a directory."""
    dir_path = tmp_path / "test_dir"
    dir_path.mkdir()
    assert dir_path.exists()
    assert delete_path_robustly(str(dir_path), "test directory") is True
    assert not dir_path.exists()


def test_delete_path_robustly_dir_with_readonly_file(tmp_path: Path):
    """Test deleting a directory that contains a read-only file."""
    dir_path = tmp_path / "readonly_dir"
    dir_path.mkdir()
    file_path = dir_path / "readonly.txt"
    file_path.write_text("readonly")
    os.chmod(file_path, stat.S_IREAD)
    assert dir_path.exists()
    assert file_path.exists()

    assert delete_path_robustly(str(dir_path), "directory with read-only file") is True
    assert not dir_path.exists()


def test_delete_path_robustly_non_existent_path(tmp_path: Path):
    """Test deleting a path that does not exist."""
    non_existent = tmp_path / "non_existent"
    assert delete_path_robustly(str(non_existent), "non existent path") is True


def test_delete_path_robustly_invalid_inputs():
    """Test deleting with invalid path or description."""
    with pytest.raises(MissingArgumentError):
        delete_path_robustly("", "description")

    with pytest.raises(MissingArgumentError):
        delete_path_robustly("path", "")

    with pytest.raises(MissingArgumentError):
        delete_path_robustly(None, "description")  # type: ignore


def test_is_server_running_true():
    """Test is_server_running when process is found."""
    with patch(
        "bedrock_server_manager.core.system.base.core_process.get_verified_bedrock_process"
    ) as mock_get:
        mock_get.return_value = MagicMock()
        assert is_server_running("server", "/path/to/server", "/path/to/config") is True


def test_is_server_running_false():
    """Test is_server_running when process is not found."""
    with patch(
        "bedrock_server_manager.core.system.base.core_process.get_verified_bedrock_process"
    ) as mock_get:
        mock_get.return_value = None
        assert (
            is_server_running("server", "/path/to/server", "/path/to/config") is False
        )


def test_resource_monitor_real_process():
    """Test ResourceMonitor with a real short-lived process."""
    monitor = ResourceMonitor()

    # Start a sleep process
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(2)"])
    try:
        # Give psutil time to hook into it
        time.sleep(0.1)
        ps_proc = psutil.Process(process.pid)

        stats = monitor.get_stats(ps_proc)
        assert stats is not None
        assert "cpu_percent" in stats
        assert "memory_mb" in stats
        assert "uptime" in stats
        assert isinstance(stats["cpu_percent"], float)
        assert isinstance(stats["memory_mb"], float)
        assert isinstance(stats["pid"], int)
        assert stats["pid"] == process.pid

        # Test a second time to ensure baseline was set and we get valid CPU diff
        time.sleep(0.5)
        stats2 = monitor.get_stats(ps_proc)
        assert stats2 is not None
        assert isinstance(stats2["cpu_percent"], float)

    finally:
        process.terminate()
        process.wait()


def test_resource_monitor_no_psutil():
    """Test ResourceMonitor behaves when psutil is 'unavailable'."""
    with patch("bedrock_server_manager.core.system.base.PSUTIL_AVAILABLE", False):
        monitor = ResourceMonitor()
        assert monitor.get_stats(MagicMock()) is None


def test_resource_monitor_invalid_process():
    """Test ResourceMonitor handles invalid process object."""
    monitor = ResourceMonitor()
    with pytest.raises(TypeError):
        monitor.get_stats("not a process")  # type: ignore


def test_resource_monitor_dead_process():
    """Test ResourceMonitor handles process that has died."""
    monitor = ResourceMonitor()

    # Passing a mock that has an exception during `oneshot()` will likely cause AttributeError
    # on context manager enter, so we instead mock `cpu_percent` to raise `NoSuchProcess`.
    mock_proc = MagicMock()
    mock_proc.pid = 99999999  # Some nonexistent pid
    mock_proc.cpu_percent.side_effect = psutil.NoSuchProcess(mock_proc.pid)

    assert monitor.get_stats(mock_proc) is None
