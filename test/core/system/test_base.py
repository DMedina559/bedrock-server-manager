import pytest
import os
import shutil
import stat
import tempfile
from unittest.mock import patch, MagicMock

from bedrock_server_manager.core.system.base import (
    check_internet_connectivity,
    set_server_folder_permissions,
    delete_path_robustly,
    ResourceMonitor,
    is_server_running,
)
from bedrock_server_manager.error import (
    InternetConnectivityError,
    PermissionsError,
    AppFileNotFoundError,
)


# Helper to create a dummy file
def create_dummy_file(path, content=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


# Test for check_internet_connectivity
@patch("socket.create_connection")
def test_check_internet_connectivity_success(mock_socket):
    check_internet_connectivity()
    mock_socket.assert_called_once()


@patch("socket.create_connection", side_effect=TimeoutError)
def test_check_internet_connectivity_timeout(mock_socket):
    with pytest.raises(InternetConnectivityError):
        check_internet_connectivity()


@patch("socket.create_connection", side_effect=OSError)
def test_check_internet_connectivity_os_error(mock_socket):
    with pytest.raises(InternetConnectivityError):
        check_internet_connectivity()


# Tests for set_server_folder_permissions
@pytest.fixture
def temp_server_dir():
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


def test_set_server_folder_permissions_linux(temp_server_dir):
    if os.name != "posix":
        pytest.skip("Linux specific test")

    server_dir = temp_server_dir
    create_dummy_file(os.path.join(server_dir, "bedrock_server"), "exe")
    create_dummy_file(os.path.join(server_dir, "test.txt"), "text")
    os.makedirs(os.path.join(server_dir, "a_dir"))

    set_server_folder_permissions(server_dir)

    assert stat.S_IMODE(os.stat(server_dir).st_mode) == 0o775
    assert (
        stat.S_IMODE(os.stat(os.path.join(server_dir, "bedrock_server")).st_mode)
        == 0o775
    )
    assert stat.S_IMODE(os.stat(os.path.join(server_dir, "test.txt")).st_mode) == 0o664
    assert stat.S_IMODE(os.stat(os.path.join(server_dir, "a_dir")).st_mode) == 0o775


def test_set_server_folder_permissions_windows(temp_server_dir):
    if os.name != "nt":
        pytest.skip("Windows specific test")

    server_dir = temp_server_dir
    test_file = os.path.join(server_dir, "test.txt")
    create_dummy_file(test_file)

    # Make file read-only
    os.chmod(test_file, stat.S_IREAD)

    set_server_folder_permissions(server_dir)

    assert os.access(test_file, os.W_OK)


def test_set_server_folder_permissions_non_existent_dir():
    with pytest.raises(AppFileNotFoundError):
        set_server_folder_permissions("non_existent_dir")


@pytest.mark.skipif(os.name != "posix", reason="Linux specific test")
@patch("os.chmod", side_effect=OSError)
def test_set_server_folder_permissions_os_error_on_chmod(mock_chmod, temp_server_dir):
    with pytest.raises(PermissionsError):
        set_server_folder_permissions(temp_server_dir)


@pytest.mark.skipif(os.name != "posix", reason="Linux specific test")
@patch("os.chown", side_effect=OSError)
def test_set_server_folder_permissions_os_error_on_chown(mock_chown, temp_server_dir):
    with pytest.raises(PermissionsError):
        set_server_folder_permissions(temp_server_dir)


# Tests for delete_path_robustly
def test_delete_path_robustly_file(temp_server_dir):
    file_path = os.path.join(temp_server_dir, "test.txt")
    create_dummy_file(file_path)
    assert os.path.exists(file_path)
    delete_path_robustly(file_path, "test file")
    assert not os.path.exists(file_path)


def test_delete_path_robustly_readonly_file(temp_server_dir):
    file_path = os.path.join(temp_server_dir, "readonly.txt")
    create_dummy_file(file_path)
    os.chmod(file_path, stat.S_IREAD)
    assert os.path.exists(file_path)
    delete_path_robustly(file_path, "readonly test file")
    assert not os.path.exists(file_path)


def test_delete_path_robustly_dir(temp_server_dir):
    dir_path = os.path.join(temp_server_dir, "a_dir")
    os.makedirs(dir_path)
    assert os.path.exists(dir_path)
    delete_path_robustly(dir_path, "test directory")
    assert not os.path.exists(dir_path)


def test_delete_path_robustly_non_existent_path(temp_server_dir):
    non_existent_path = os.path.join(temp_server_dir, "non_existent")
    assert delete_path_robustly(non_existent_path, "non existent path") is True


# Tests for ResourceMonitor
from collections import namedtuple


@patch("bedrock_server_manager.core.system.base.PSUTIL_AVAILABLE", True)
@patch("psutil.Process")
def test_resource_monitor_get_stats(mock_process):
    mock_proc_instance = mock_process.return_value
    mock_proc_instance.pid = 123
    cpu_times = namedtuple("cpu_times", ["user", "system"])
    mock_proc_instance.cpu_times.return_value = cpu_times(0.5, 0.5)  # user, system
    mock_proc_instance.memory_info.return_value.rss = 1024 * 1024 * 100  # 100MB
    mock_proc_instance.create_time.return_value = 0

    monitor = ResourceMonitor()

    # First call should be 0% cpu
    stats = monitor.get_stats(mock_proc_instance)
    assert stats["cpu_percent"] == 0.0

    # Second call to calculate cpu
    with patch("time.time", return_value=1):
        stats = monitor.get_stats(mock_proc_instance)
        assert stats["cpu_percent"] == 0.0

    # Third call to calculate cpu
    mock_proc_instance.cpu_times.return_value = cpu_times(1.0, 1.0)
    with patch("time.time", return_value=2):
        with patch("psutil.cpu_count", return_value=1):
            stats = monitor.get_stats(mock_proc_instance)
            assert stats["cpu_percent"] > 0.0
            assert stats["memory_mb"] == 100.0


@patch("bedrock_server_manager.core.system.base.PSUTIL_AVAILABLE", False)
def test_resource_monitor_no_psutil():
    monitor = ResourceMonitor()
    assert monitor.get_stats(MagicMock()) is None


# Tests for is_server_running
@patch("bedrock_server_manager.core.system.process.get_verified_bedrock_process")
def test_is_server_running_true(mock_get_verified):
    mock_get_verified.return_value = MagicMock()
    assert is_server_running("server", "/path/to/server", "/path/to/config") is True


@patch("bedrock_server_manager.core.system.process.get_verified_bedrock_process")
def test_is_server_running_false(mock_get_verified):
    mock_get_verified.return_value = None
    assert is_server_running("server", "/path/to/server", "/path/to/config") is False
