"""Tests for system process management utilities in bedrock_server_manager.core.system.process."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    exe_path = server.paths.bedrock_executable_path
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


async def test_verify_process_identity_success(real_bedrock_server):
    server = real_bedrock_server
    await server.start()
    await verify_process_identity(
        server.process._process.pid,
        expected_executable_path=server.paths.bedrock_executable_path,
        expected_cwd=server.paths.server_dir,
    )


@pytest.mark.parametrize("criterion", ["executable", "cwd", "arguments"])
async def test_verify_process_identity_mismatch(
    real_bedrock_server, tmp_path, criterion
):
    server = real_bedrock_server
    await server.start()
    criteria = {
        "executable": (
            "expected_executable_path",
            str(tmp_path / "other"),
            "Executable path mismatch",
        ),
        "cwd": ("expected_cwd", str(tmp_path), "CWD mismatch"),
        "arguments": (
            "expected_command_args",
            ["--not-a-server-argument"],
            "Argument mismatch",
        ),
    }
    key, value, message = criteria[criterion]
    with pytest.raises(ServerProcessError, match=message):
        await verify_process_identity(server.process._process.pid, **{key: value})
    assert await server.is_running()


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


async def test_get_verified_bedrock_process_success(real_bedrock_server):
    server = real_bedrock_server
    await server.start()
    process = await get_verified_bedrock_process(
        server.server_name, server.paths.server_dir, server.paths.app_config_dir
    )
    assert process.pid == server.process._process.pid
    assert process.is_running()


async def test_get_verified_bedrock_process_no_pid(real_bedrock_server):
    server = real_bedrock_server
    assert not Path(server.get_pid_file_path()).exists()
    assert (
        await get_verified_bedrock_process(
            server.server_name, server.paths.server_dir, server.paths.app_config_dir
        )
        is None
    )


async def test_get_verified_bedrock_process_stale_pid(real_bedrock_server):
    server = real_bedrock_server
    await server.start()
    pid = server.process._process.pid
    await server.stop()
    path = server.get_pid_file_path()
    await write_pid_to_file(path, pid)
    assert (
        await get_verified_bedrock_process(
            server.server_name, server.paths.server_dir, server.paths.app_config_dir
        )
        is None
    )
    assert not Path(path).exists()


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


async def test_terminate_process_by_pid_graceful(real_bedrock_server):
    server = real_bedrock_server
    await server.start()
    child = server.process._process
    await terminate_process_by_pid(child.pid)
    import asyncio

    await asyncio.wait_for(child.wait(), 5)
    assert child.returncode is not None
    assert not await is_process_running(child.pid)


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
    exe_path = server.paths.bedrock_executable_path
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
    import asyncio

    await asyncio.sleep(0.5)
    assert await is_process_running(pid) is False


async def test_detached_child_survives_launcher_event_loop(tmp_path):
    import asyncio
    import sys

    from bedrock_server_manager.utils.threads import run_in_thread

    request = tmp_path / "request"
    acknowledgement = tmp_path / "acknowledgement"
    child_script = tmp_path / "child.py"
    child_script.write_text(
        "import sys, time\n"
        "from pathlib import Path\n"
        "request, acknowledgement = map(Path, sys.argv[1:])\n"
        "deadline = time.monotonic() + 10\n"
        "while not request.exists() and time.monotonic() < deadline:\n"
        "    time.sleep(0.01)\n"
        "if request.exists():\n"
        "    acknowledgement.write_text('child survived')\n"
    )
    command = [sys.executable, str(child_script), str(request), str(acknowledgement)]
    pid_file = tmp_path / "launcher.pid"

    def launch_on_temporary_loop():
        return asyncio.run(launch_detached_process(command, str(pid_file)))

    try:
        pid = await run_in_thread(launch_on_temporary_loop)
        assert int(pid_file.read_text()) == pid
        # The launching loop has closed before the child receives this request.
        request.touch()
        async with asyncio.timeout(5):
            while not acknowledgement.exists():
                await asyncio.sleep(0.01)
        assert acknowledgement.read_text() == "child survived"
    finally:
        request.touch()
