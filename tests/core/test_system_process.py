"""Tests for system process management utilities in bedrock_server_manager.core.system.process."""

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import psutil
import pytest

from bedrock_server_manager.config import GUARD_VARIABLE
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
    MissingArgumentError,
    PermissionsError,
    ServerProcessError,
    ServerStopError,
    SystemError,
)

# --- PID File Path Tests ---


async def test_get_pid_file_path(tmp_path: Path):
    """Test get_pid_file_path with valid inputs."""
    config_dir = str(tmp_path)
    pid_filename = "test.pid"
    expected = os.path.join(config_dir, pid_filename)
    assert await get_pid_file_path(config_dir, pid_filename) == expected


async def test_get_pid_file_path_invalid():
    """Test get_pid_file_path with invalid inputs."""
    with pytest.raises(AppFileNotFoundError):
        await get_pid_file_path("", "test.pid")
    with pytest.raises(AppFileNotFoundError):
        await get_pid_file_path("/nonexistent/dir", "test.pid")
    with pytest.raises(MissingArgumentError):
        await get_pid_file_path(str(Path.cwd()), "")


async def test_get_bedrock_server_pid_file_path(tmp_path: Path):
    """Test get_bedrock_server_pid_file_path with valid inputs."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    server_name = "myserver"
    server_config_dir = config_dir / server_name
    server_config_dir.mkdir()

    expected = os.path.join(str(server_config_dir), f"bedrock_{server_name}.pid")
    assert (
        await get_bedrock_server_pid_file_path(server_name, str(config_dir)) == expected
    )


async def test_get_bedrock_server_pid_file_path_invalid(tmp_path: Path):
    """Test get_bedrock_server_pid_file_path with invalid inputs."""
    with pytest.raises(MissingArgumentError):
        await get_bedrock_server_pid_file_path("", str(tmp_path))
    with pytest.raises(MissingArgumentError):
        await get_bedrock_server_pid_file_path("server", "")
    with pytest.raises(AppFileNotFoundError):
        await get_bedrock_server_pid_file_path("server", "/nonexistent/config")

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    with pytest.raises(AppFileNotFoundError):
        # Server subfolder doesn't exist
        await get_bedrock_server_pid_file_path("server", str(config_dir))


async def test_get_bedrock_launcher_pid_file_path(tmp_path: Path):
    """Test get_bedrock_launcher_pid_file_path creates dir and returns path."""
    config_dir = tmp_path / "launcher_config"
    server_name = "myserver"

    expected = os.path.join(str(config_dir), f"bedrock_{server_name}_launcher.pid")
    assert (
        await get_bedrock_launcher_pid_file_path(server_name, str(config_dir))
        == expected
    )
    assert config_dir.exists()


async def test_get_bedrock_launcher_pid_file_path_invalid(tmp_path: Path):
    """Test get_bedrock_launcher_pid_file_path invalid inputs."""
    with pytest.raises(MissingArgumentError):
        await get_bedrock_launcher_pid_file_path("", str(tmp_path))
    with pytest.raises(MissingArgumentError):
        await get_bedrock_launcher_pid_file_path("server", "")


# --- PID File I/O Tests ---


async def test_read_pid_from_file_success(tmp_path: Path):
    """Test reading a valid PID from file."""
    pid_file = tmp_path / "test.pid"
    pid_file.write_text("1234")
    assert await read_pid_from_file(str(pid_file)) == 1234

    pid_file.write_text("  5678  \n")
    assert await read_pid_from_file(str(pid_file)) == 5678


async def test_read_pid_from_file_not_found(tmp_path: Path):
    """Test reading from non-existent PID file."""
    pid_file = tmp_path / "nonexistent.pid"
    assert await read_pid_from_file(str(pid_file)) is None


async def test_read_pid_from_file_invalid(tmp_path: Path):
    """Test reading invalid data from PID file."""
    pid_file = tmp_path / "test.pid"
    pid_file.write_text("not_a_pid")
    # Returns None now instead of raising
    assert await read_pid_from_file(str(pid_file)) is None


async def test_read_pid_from_file_missing_arg():
    """Test read_pid_from_file with missing argument."""
    with pytest.raises(MissingArgumentError):
        await read_pid_from_file("")


async def test_write_pid_to_file(tmp_path: Path):
    """Test writing PID to file."""
    pid_file = tmp_path / "nested" / "test.pid"
    await write_pid_to_file(str(pid_file), 9999)
    assert pid_file.read_text().strip() == "9999"


async def test_write_pid_to_file_invalid(tmp_path: Path):
    """Test write_pid_to_file with invalid inputs."""
    with pytest.raises(MissingArgumentError):
        await write_pid_to_file("", 1234)
    with pytest.raises(MissingArgumentError):
        await write_pid_to_file(str(tmp_path / "test.pid"), "1234")  # type: ignore


async def test_remove_pid_file_if_exists(tmp_path: Path):
    """Test removing an existing PID file."""
    pid_file = tmp_path / "test.pid"
    pid_file.write_text("1234")
    assert await remove_pid_file_if_exists(str(pid_file)) is True
    assert not pid_file.exists()


async def test_remove_pid_file_not_exists(tmp_path: Path):
    """Test removing a non-existent PID file."""
    pid_file = tmp_path / "nonexistent.pid"
    assert await remove_pid_file_if_exists(str(pid_file)) is True


async def test_remove_pid_file_missing_arg():
    """Test remove_pid_file_if_exists missing argument."""
    with pytest.raises(MissingArgumentError):
        await remove_pid_file_if_exists("")


# --- Process Execution Tests ---


async def test_guarded_process():
    """Test GuardedProcess environment injection."""
    cmd = ["echo", "test"]
    guarded = GuardedProcess(cmd)
    assert guarded.command == cmd
    assert GUARD_VARIABLE in guarded.guard_env
    assert guarded.guard_env[GUARD_VARIABLE] == "1"


async def test_launch_detached_process(tmp_path: Path, real_bedrock_server):
    """Test launch_detached_process using the dummy executable."""
    server = real_bedrock_server
    exe_path = server.bedrock_executable_path
    cmd = [exe_path]
    launcher_pid_file = tmp_path / "launcher.pid"

    pid = await launch_detached_process(cmd, str(launcher_pid_file))

    # Process should be running
    assert await is_process_running(pid)

    # The PID should be written to the file
    assert launcher_pid_file.exists()
    assert int(launcher_pid_file.read_text().strip()) == pid

    # Cleanup
    await terminate_process_by_pid(pid)


async def test_launch_detached_process_invalid(tmp_path: Path):
    """Test launch_detached_process with invalid arguments."""
    with pytest.raises(MissingArgumentError):
        await launch_detached_process([], str(tmp_path / "launcher.pid"))
    with pytest.raises(MissingArgumentError):
        await launch_detached_process(["cmd"], "")


async def test_launch_detached_process_not_found(tmp_path: Path):
    """Test launch_detached_process when executable is not found."""
    cmd = ["nonexistent_executable"]
    launcher_pid_file = tmp_path / "launcher.pid"

    with pytest.raises(AppFileNotFoundError):
        await launch_detached_process(cmd, str(launcher_pid_file))


# --- Process Status & Verification Tests ---


@patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True)
@patch("psutil.pid_exists", return_value=True)
async def test_is_process_running_true(mock_pid_exists):
    """Test is_process_running when process exists."""
    assert await is_process_running(1234) is True
    mock_pid_exists.assert_called_once_with(1234)


@patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True)
@patch("psutil.pid_exists", return_value=False)
async def test_is_process_running_false(mock_pid_exists):
    """Test is_process_running when process does not exist."""
    assert await is_process_running(1234) is False
    mock_pid_exists.assert_called_once_with(1234)


@patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", False)
async def test_is_process_running_no_psutil():
    """Test is_process_running when psutil is not available."""
    with pytest.raises(SystemError):
        await is_process_running(1234)


@patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True)
@patch("psutil.Process")
async def test_verify_process_identity_success(mock_process_class):
    """Test verify_process_identity when all criteria match."""
    mock_proc = MagicMock()
    mock_proc.name.return_value = "my_app"
    mock_proc.exe.return_value = "/path/to/my_app"
    mock_proc.cwd.return_value = "/path/to"
    mock_proc.cmdline.return_value = ["/path/to/my_app", "--arg1"]
    mock_process_class.return_value = mock_proc

    # Should not raise any exception
    await verify_process_identity(
        1234,
        expected_executable_path="/path/to/my_app",
        expected_cwd="/path/to",
        expected_command_args="--arg1",
    )


@patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True)
@patch("psutil.Process")
async def test_verify_process_identity_mismatch(mock_process_class):
    """Test verify_process_identity when criteria do not match."""
    mock_proc = MagicMock()
    mock_proc.name.return_value = "my_app"
    mock_proc.exe.return_value = "/wrong/path/my_app"
    mock_proc.cwd.return_value = "/wrong/cwd"
    mock_proc.cmdline.return_value = ["/wrong/path/my_app"]
    mock_process_class.return_value = mock_proc

    with pytest.raises(ServerProcessError) as exc_info:
        await verify_process_identity(
            1234,
            expected_executable_path="/path/to/my_app",
            expected_cwd="/path/to",
            expected_command_args="--arg1",
        )

    assert "Executable path mismatch" in str(exc_info.value)
    assert "CWD mismatch" in str(exc_info.value)
    assert "Argument mismatch" in str(exc_info.value)


@patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True)
@patch("psutil.Process")
async def test_verify_process_identity_no_such_process(mock_process_class):
    """Test verify_process_identity when process does not exist."""
    mock_process_class.side_effect = psutil.NoSuchProcess(1234)
    with pytest.raises(ServerProcessError):
        await verify_process_identity(1234, expected_executable_path="/app")


@patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True)
@patch("psutil.Process")
async def test_verify_process_identity_access_denied(mock_process_class):
    """Test verify_process_identity when access is denied."""
    mock_process_class.side_effect = psutil.AccessDenied(1234)
    with pytest.raises(PermissionsError):
        await verify_process_identity(1234, expected_executable_path="/app")


@patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", False)
async def test_verify_process_identity_no_psutil():
    """Test verify_process_identity when psutil is not available."""
    with pytest.raises(SystemError):
        await verify_process_identity(1234, expected_executable_path="/app")


async def test_verify_process_identity_missing_args():
    """Test verify_process_identity with missing arguments."""
    with pytest.raises(MissingArgumentError):
        await verify_process_identity("1234", expected_executable_path="/app")  # type: ignore
    with pytest.raises(MissingArgumentError):
        await verify_process_identity(1234)  # No criteria provided


# --- High Level Verification Tests ---


@patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True)
@patch(
    "bedrock_server_manager.core.system.process.get_bedrock_server_pid_file_path",
    new_callable=AsyncMock,
)
@patch(
    "bedrock_server_manager.core.system.process.read_pid_from_file",
    new_callable=AsyncMock,
)
@patch(
    "bedrock_server_manager.core.system.process.is_process_running",
    new_callable=AsyncMock,
)
@patch(
    "bedrock_server_manager.core.system.process.verify_process_identity",
    new_callable=AsyncMock,
)
@patch("psutil.Process")
async def test_get_verified_bedrock_process_success(
    mock_psutil_process,
    mock_verify,
    mock_is_running,
    mock_read_pid,
    mock_get_pid_path,
):
    """Test get_verified_bedrock_process on success."""
    mock_get_pid_path.return_value = "/config/myserver/bedrock_myserver.pid"
    mock_read_pid.return_value = 1234
    mock_is_running.return_value = True

    mock_proc = MagicMock()
    mock_psutil_process.return_value = mock_proc

    with patch("aiofiles.ospath.isdir", new_callable=AsyncMock, return_value=True):
        result = await get_verified_bedrock_process(
            "myserver", "/server/dir", "/config"
        )

    assert result == mock_proc
    mock_verify.assert_called_once()


@patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True)
@patch(
    "bedrock_server_manager.core.system.process.get_bedrock_server_pid_file_path",
    new_callable=AsyncMock,
)
@patch(
    "bedrock_server_manager.core.system.process.read_pid_from_file",
    new_callable=AsyncMock,
)
async def test_get_verified_bedrock_process_no_pid(mock_read_pid, mock_get_pid_path):
    """Test get_verified_bedrock_process when no PID file exists."""
    mock_get_pid_path.return_value = "/config/myserver/bedrock_myserver.pid"
    mock_read_pid.return_value = None

    with patch("aiofiles.ospath.isdir", new_callable=AsyncMock, return_value=True):
        result = await get_verified_bedrock_process(
            "myserver", "/server/dir", "/config"
        )

    assert result is None


@patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True)
@patch(
    "bedrock_server_manager.core.system.process.get_bedrock_server_pid_file_path",
    new_callable=AsyncMock,
)
@patch(
    "bedrock_server_manager.core.system.process.read_pid_from_file",
    new_callable=AsyncMock,
)
@patch(
    "bedrock_server_manager.core.system.process.is_process_running",
    new_callable=AsyncMock,
)
@patch(
    "bedrock_server_manager.core.system.process.remove_pid_file_if_exists",
    new_callable=AsyncMock,
)
async def test_get_verified_bedrock_process_stale_pid(
    mock_remove_pid,
    mock_is_running,
    mock_read_pid,
    mock_get_pid_path,
):
    """Test get_verified_bedrock_process when PID is stale (not running)."""
    mock_get_pid_path.return_value = "/config/myserver/bedrock_myserver.pid"
    mock_read_pid.return_value = 1234
    mock_is_running.return_value = False

    with patch("aiofiles.ospath.isdir", new_callable=AsyncMock, return_value=True):
        result = await get_verified_bedrock_process(
            "myserver", "/server/dir", "/config"
        )

    assert result is None
    mock_remove_pid.assert_called_once_with("/config/myserver/bedrock_myserver.pid")


@patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", False)
async def test_get_verified_bedrock_process_no_psutil():
    """Test get_verified_bedrock_process when psutil is unavailable."""
    assert (
        await get_verified_bedrock_process("myserver", "/server/dir", "/config") is None
    )


async def test_get_verified_bedrock_process_invalid_args():
    """Test get_verified_bedrock_process with invalid arguments."""
    assert await get_verified_bedrock_process("", "/server/dir", "/config") is None
    assert await get_verified_bedrock_process("server", "", "/config") is None
    assert await get_verified_bedrock_process("server", "/server/dir", "") is None


# --- Process Termination Tests ---


@patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True)
@patch("psutil.Process")
async def test_terminate_process_by_pid_graceful(mock_process_class):
    """Test terminate_process_by_pid graceful shutdown."""
    mock_proc = MagicMock()
    mock_process_class.return_value = mock_proc

    await terminate_process_by_pid(1234)

    mock_proc.terminate.assert_called_once()
    mock_proc.wait.assert_called_once_with(timeout=5)
    mock_proc.kill.assert_not_called()


@patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True)
@patch("psutil.Process")
async def test_terminate_process_by_pid_force_kill(mock_process_class):
    """Test terminate_process_by_pid force kill after graceful timeout."""
    mock_proc = MagicMock()
    # First wait raises TimeoutExpired
    mock_proc.wait.side_effect = [psutil.TimeoutExpired(10), None]
    mock_process_class.return_value = mock_proc

    await terminate_process_by_pid(1234)

    mock_proc.terminate.assert_called_once()
    mock_proc.kill.assert_called_once()
    # Wait is called twice: once for terminate, once for kill
    assert mock_proc.wait.call_count == 2


@patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True)
@patch("psutil.Process")
async def test_terminate_process_by_pid_no_such_process(mock_process_class):
    """Test terminate_process_by_pid when process already exited."""
    mock_process_class.side_effect = psutil.NoSuchProcess(1234)

    # Should not raise
    await terminate_process_by_pid(1234)


@patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True)
@patch("psutil.Process")
async def test_terminate_process_by_pid_access_denied(mock_process_class):
    """Test terminate_process_by_pid when access is denied."""
    mock_process_class.side_effect = psutil.AccessDenied(1234)

    with pytest.raises(PermissionsError):
        await terminate_process_by_pid(1234)


@patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", False)
async def test_terminate_process_by_pid_no_psutil():
    """Test terminate_process_by_pid when psutil is missing."""
    with pytest.raises(SystemError):
        await terminate_process_by_pid(1234)


async def test_terminate_process_by_pid_invalid_args():
    """Test terminate_process_by_pid with invalid args."""
    with pytest.raises(MissingArgumentError):
        await terminate_process_by_pid("1234")  # type: ignore
    with pytest.raises(ServerStopError):
        await terminate_process_by_pid(1234, terminate_timeout=-1)
    with pytest.raises(ServerStopError):
        await terminate_process_by_pid(1234, kill_timeout=-1)


async def test_dummy_launch_and_verify(tmp_path: Path, real_bedrock_server):
    """Test process lifecycle using the real dummy binary."""
    # Use real_bedrock_server fixture to set up a valid dummy binary
    server = real_bedrock_server
    exe_path = server.bedrock_executable_path
    cmd = [exe_path]

    launcher_pid_file = tmp_path / "launcher.pid"

    # 1. Launch the process
    pid = await launch_detached_process(cmd, str(launcher_pid_file))

    assert launcher_pid_file.exists()

    # 2. Verify process is running
    assert await is_process_running(pid) is True

    # 3. Verify process identity matches the dummy binary
    # Note: cwd may default to current app path if not specified in the detached process Popen call
    await verify_process_identity(
        pid,
        expected_executable_path=exe_path,
    )

    # 4. Terminate process gracefully
    await terminate_process_by_pid(pid)

    # 5. Verify process is no longer running
    import time

    time.sleep(0.5)
    assert await is_process_running(pid) is False
