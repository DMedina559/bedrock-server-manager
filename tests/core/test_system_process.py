"""Tests for system process management utilities in bedrock_server_manager.core.system.process."""

import os
from pathlib import Path
from unittest.mock import patch

import psutil
import pytest

from bedrock_server_manager.config import GUARD_VARIABLE
from bedrock_server_manager.core.system.process import (
    GuardedProcess,
    get_bedrock_server_pid_file_path,
    get_pid_file_path,
    get_verified_bedrock_process,
    is_process_running,
    read_pid_from_file,
    remove_pid_file_if_exists,
    verify_process_identity,
    write_pid_to_file,
)
from bedrock_server_manager.error import (
    AppFileNotFoundError,
    MissingArgumentError,
    PermissionsError,
    ServerProcessError,
    SystemError,
)


async def test_pid_file_paths_and_io(tmp_path: Path):
    """Test PID path resolution and PID file read/write/remove operations."""
    config_dir = str(tmp_path)
    expected = os.path.join(config_dir, "runtime", "test.pid")
    assert await get_pid_file_path(config_dir, "test.pid") == expected

    with pytest.raises(AppFileNotFoundError):
        await get_pid_file_path("", "test.pid")
    with pytest.raises(AppFileNotFoundError):
        await get_pid_file_path("/nonexistent/dir", "test.pid")
    with pytest.raises(MissingArgumentError):
        await get_pid_file_path(str(Path.cwd()), "")

    srv_cfg_root = tmp_path / "config"
    srv_cfg_root.mkdir()
    server_name = "myserver"
    with pytest.raises(AppFileNotFoundError):
        await get_bedrock_server_pid_file_path(server_name, str(srv_cfg_root))

    server_config_dir = srv_cfg_root / "runtime" / "servers" / server_name
    server_config_dir.mkdir(parents=True)
    assert await get_bedrock_server_pid_file_path(
        server_name, str(srv_cfg_root)
    ) == os.path.join(str(server_config_dir), f"bedrock_{server_name}.pid")

    with pytest.raises(MissingArgumentError):
        await get_bedrock_server_pid_file_path("", str(tmp_path))
    with pytest.raises(MissingArgumentError):
        await get_bedrock_server_pid_file_path("server", "")
    with pytest.raises(AppFileNotFoundError):
        await get_bedrock_server_pid_file_path("server", "/nonexistent/config")

    pid_file = tmp_path / "test.pid"
    assert await read_pid_from_file(str(tmp_path / "nonexistent.pid")) is None
    pid_file.write_text("1234")
    assert await read_pid_from_file(str(pid_file)) == 1234
    pid_file.write_text("  5678  \n")
    assert await read_pid_from_file(str(pid_file)) == 5678
    pid_file.write_text("not_a_pid")
    assert await read_pid_from_file(str(pid_file)) is None
    with pytest.raises(MissingArgumentError):
        await read_pid_from_file("")

    nested_pid = tmp_path / "nested" / "test.pid"
    await write_pid_to_file(str(nested_pid), 9999)
    assert nested_pid.read_text().strip() == "9999"
    with pytest.raises(MissingArgumentError):
        await write_pid_to_file("", 1234)
    with pytest.raises(MissingArgumentError):
        await write_pid_to_file(str(pid_file), "1234")  # type: ignore

    assert await remove_pid_file_if_exists(str(pid_file)) is True
    assert not pid_file.exists()
    assert await remove_pid_file_if_exists(str(pid_file)) is True
    with pytest.raises(MissingArgumentError):
        await remove_pid_file_if_exists("")


async def test_guarded_process_and_psutil_edge_cases():
    """Test GuardedProcess and mocked psutil error branches."""
    cmd = ["echo", "test"]
    guarded = GuardedProcess(cmd)
    assert guarded.command == cmd
    assert guarded.guard_env.get(GUARD_VARIABLE) == "1"

    with (
        patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True),
        patch("psutil.pid_exists", return_value=True) as mock_exists,
    ):
        assert await is_process_running(1234) is True
        mock_exists.assert_called_once_with(1234)

    with (
        patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True),
        patch("psutil.pid_exists", return_value=False) as mock_exists,
    ):
        assert await is_process_running(1234) is False
        mock_exists.assert_called_once_with(1234)

    with patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", False):
        with pytest.raises(SystemError):
            await is_process_running(1234)
        with pytest.raises(SystemError):
            await verify_process_identity(1234, expected_executable_path="/app")
        assert (
            await get_verified_bedrock_process("myserver", "/server/dir", "/config")
            is None
        )

    with (
        patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True),
        patch("psutil.Process", side_effect=psutil.NoSuchProcess(1234)),
    ):
        with pytest.raises(ServerProcessError):
            await verify_process_identity(1234, expected_executable_path="/app")

    with (
        patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True),
        patch("psutil.Process", side_effect=psutil.AccessDenied(1234)),
    ):
        with pytest.raises(PermissionsError):
            await verify_process_identity(1234, expected_executable_path="/app")

    with pytest.raises(MissingArgumentError):
        await verify_process_identity("1234", expected_executable_path="/app")  # type: ignore
    with pytest.raises(MissingArgumentError):
        await verify_process_identity(1234)

    assert await get_verified_bedrock_process("", "/server/dir", "/config") is None
    assert await get_verified_bedrock_process("server", "", "/config") is None
    assert await get_verified_bedrock_process("server", "/server/dir", "") is None


async def test_verify_and_get_bedrock_process_with_real_server(
    real_bedrock_server, tmp_path
):
    server = real_bedrock_server
    assert not Path(server.get_pid_file_path()).exists()
    assert (
        await get_verified_bedrock_process(
            server.server_name, server.paths.server_dir, server.paths.app_config_dir
        )
        is None
    )

    await server.start()
    pid = server.process._process.pid
    await verify_process_identity(
        pid,
        expected_executable_path=server.paths.bedrock_executable_path,
        expected_cwd=server.paths.server_dir,
    )
    for key, value, message in (
        (
            "expected_executable_path",
            str(tmp_path / "other"),
            "Executable path mismatch",
        ),
        ("expected_cwd", str(tmp_path), "CWD mismatch"),
        ("expected_command_args", ["--not-a-server-argument"], "Argument mismatch"),
    ):
        with pytest.raises(ServerProcessError, match=message):
            await verify_process_identity(pid, **{key: value})
    assert await server.is_running()

    process = await get_verified_bedrock_process(
        server.server_name, server.paths.server_dir, server.paths.app_config_dir
    )
    assert process.pid == pid
    assert process.is_running()

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
