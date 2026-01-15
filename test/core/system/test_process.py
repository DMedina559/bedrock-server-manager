import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from bedrock_server_manager.core.system.process import (
    GuardedProcess,
    get_bedrock_launcher_pid_file_path,
    get_bedrock_server_pid_file_path,
    get_pid_file_path,
    get_verified_bedrock_process,
    is_process_running,
    launch_detached_process,
    read_pid_from_file,
    remove_pid_file_if_exists,
    terminate_process_by_pid,
    verify_process_identity,
    write_pid_to_file,
)
from bedrock_server_manager.error import (
    AppFileNotFoundError,
    FileOperationError,
    MissingArgumentError,
    PermissionsError,
    ServerProcessError,
    SystemError,
)


@pytest.fixture
def temp_config_dir(tmp_path):
    """Creates a temporary config directory for tests."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def temp_server_dir(tmp_path):
    """Creates a temporary server directory for tests."""
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    return server_dir


class TestPidFileManagement:
    def test_get_pid_file_path(self, temp_config_dir):
        path = get_pid_file_path(str(temp_config_dir), "test.pid")
        assert path == os.path.join(str(temp_config_dir), "test.pid")

    def test_get_bedrock_server_pid_file_path(self, temp_config_dir):
        server_config_dir = temp_config_dir / "my-server"
        server_config_dir.mkdir()
        path = get_bedrock_server_pid_file_path("my-server", str(temp_config_dir))
        assert path == os.path.join(str(server_config_dir), "bedrock_my-server.pid")

    def test_get_bedrock_launcher_pid_file_path(self, temp_config_dir):
        path = get_bedrock_launcher_pid_file_path("my-server", str(temp_config_dir))
        assert path == os.path.join(
            str(temp_config_dir), "bedrock_my-server_launcher.pid"
        )

    def test_read_write_remove_pid_file(self, temp_config_dir):
        pid_file = os.path.join(str(temp_config_dir), "test.pid")

        # Write
        write_pid_to_file(pid_file, 12345)

        # Read
        pid = read_pid_from_file(pid_file)
        assert pid == 12345

        # Remove
        remove_pid_file_if_exists(pid_file)
        assert not os.path.exists(pid_file)

    def test_read_pid_from_non_existent_file(self, temp_config_dir):
        pid = read_pid_from_file(os.path.join(str(temp_config_dir), "non_existent.pid"))
        assert pid is None

    def test_read_pid_from_invalid_file(self, temp_config_dir):
        pid_file = os.path.join(str(temp_config_dir), "invalid.pid")
        with open(pid_file, "w") as f:
            f.write("not-a-pid")

        with pytest.raises(FileOperationError):
            read_pid_from_file(pid_file)


@patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True)
@patch("psutil.pid_exists")
def test_is_process_running(mock_pid_exists):
    mock_pid_exists.return_value = True
    assert is_process_running(123)

    mock_pid_exists.return_value = False
    assert not is_process_running(456)


@patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True)
@patch("psutil.Process")
def test_verify_process_identity(mock_process):
    mock_proc = MagicMock()
    mock_proc.name.return_value = "bedrock_server"
    mock_proc.exe.return_value = "/server/bedrock_server"
    mock_proc.cwd.return_value = "/server"
    mock_proc.cmdline.return_value = ["/server/bedrock_server"]
    mock_process.return_value = mock_proc

    # Success
    verify_process_identity(
        123, expected_executable_path="/server/bedrock_server", expected_cwd="/server"
    )

    # Failure
    with pytest.raises(ServerProcessError):
        verify_process_identity(
            123, expected_executable_path="/wrong/path", expected_cwd="/server"
        )


@patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True)
@patch("bedrock_server_manager.core.system.process.read_pid_from_file")
@patch("bedrock_server_manager.core.system.process.is_process_running")
@patch("bedrock_server_manager.core.system.process.verify_process_identity")
@patch("psutil.Process")
def test_get_verified_bedrock_process(
    mock_psutil_process,
    mock_verify,
    mock_is_running,
    mock_read_pid,
    temp_server_dir,
    temp_config_dir,
):
    (temp_config_dir / "my-server").mkdir()
    mock_read_pid.return_value = 123
    mock_is_running.return_value = True

    # Success
    get_verified_bedrock_process(
        "my-server", str(temp_server_dir), str(temp_config_dir)
    )
    mock_verify.assert_called_once()

    # Not running
    mock_is_running.return_value = False
    assert (
        get_verified_bedrock_process(
            "my-server", str(temp_server_dir), str(temp_config_dir)
        )
        is None
    )


@patch("bedrock_server_manager.core.system.process.GuardedProcess")
def test_launch_detached_process(mock_guarded_process):
    mock_popen = MagicMock()
    mock_popen.pid = 12345
    mock_guarded_process.return_value.popen.return_value = mock_popen

    with patch(
        "bedrock_server_manager.core.system.process.write_pid_to_file"
    ) as mock_write_pid:
        pid = launch_detached_process(["my_command"], "launcher.pid")
        assert pid == 12345
        mock_write_pid.assert_called_once_with("launcher.pid", 12345)


import psutil


@patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True)
@patch("psutil.Process")
def test_terminate_process_by_pid(mock_process):
    mock_proc = MagicMock()
    mock_process.return_value = mock_proc

    # Graceful termination
    terminate_process_by_pid(123)
    mock_proc.terminate.assert_called_once()
    mock_proc.wait.assert_called_once()
    mock_proc.kill.assert_not_called()

    # Forceful kill
    mock_proc.wait.side_effect = [psutil.TimeoutExpired(seconds=1, pid=123), None]
    terminate_process_by_pid(123)
    mock_proc.kill.assert_called_once()


def test_guarded_process():
    with patch("subprocess.run") as mock_run:
        gp = GuardedProcess(["my_command"])
        gp.run()
        mock_run.assert_called_once_with(["my_command"], env=gp.guard_env)

    with patch("subprocess.Popen") as mock_popen:
        gp = GuardedProcess(["my_command"])
        gp.popen()
        mock_popen.assert_called_once_with(["my_command"], env=gp.guard_env)
