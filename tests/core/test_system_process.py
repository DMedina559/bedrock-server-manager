"""Tests for system process management utilities in bedrock_server_manager.core.system.process."""

import os
from pathlib import Path
from unittest.mock import patch

import psutil
import pytest

from bedrock_server_manager.config import GUARD_VARIABLE
from bedrock_server_manager.core.system.process import (
    GuardedProcess,
    clear_untracked_scan_cache,
    find_untracked_server_process,
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

    # Test orphan process recovery when PID file is unlinked while server is running
    pid_file_path = Path(server.get_pid_file_path())
    assert pid_file_path.exists()
    pid_file_path.unlink()
    assert not pid_file_path.exists()

    recovered_process = await get_verified_bedrock_process(
        server.server_name, server.paths.server_dir, server.paths.app_config_dir
    )
    assert recovered_process is not None
    assert recovered_process.pid == pid
    assert pid_file_path.exists()
    assert await read_pid_from_file(str(pid_file_path)) == pid

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


def test_find_untracked_server_process_psutil(tmp_path: Path):
    """Test process scanning via psutil matching cwd or exe."""
    server_dir = str(tmp_path / "myserver")
    os.makedirs(server_dir, exist_ok=True)
    exe_name = "bedrock_server.exe" if os.name == "nt" else "bedrock_server"
    exe_path = os.path.join(server_dir, exe_name)
    Path(exe_path).touch()

    class MockProc:
        def __init__(
            self, pid, name, cwd_val=None, exe_val=None, raises_in_oneshot=False
        ):
            self.pid = pid
            self.info = {"pid": pid, "name": name}
            self._cwd = cwd_val
            self._exe = exe_val
            self._raises = raises_in_oneshot

        def oneshot(self):
            class Ctx:
                def __init__(self, raises):
                    self.raises = raises

                def __enter__(self):
                    if self.raises:
                        raise psutil.NoSuchProcess(999)
                    return self

                def __exit__(self, *args):
                    pass

            return Ctx(self._raises)

        def cwd(self):
            if isinstance(self._cwd, Exception):
                raise self._cwd
            return self._cwd

        def exe(self):
            if isinstance(self._exe, Exception):
                raise self._exe
            return self._exe

    # Case 1: CWD match
    proc1 = MockProc(101, exe_name, cwd_val=server_dir, exe_val="/some/other/exe")
    with (
        patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True),
        patch("psutil.process_iter", return_value=[proc1]),
    ):
        assert find_untracked_server_process(server_dir) == 101

    # Case 2: CWD raises AccessDenied, Exe matches
    proc2 = MockProc(
        102,
        exe_name,
        cwd_val=psutil.AccessDenied(102),
        exe_val=exe_path,
    )
    with (
        patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True),
        patch("psutil.process_iter", return_value=[proc2]),
    ):
        assert find_untracked_server_process(server_dir) == 102

    # Case 3: Name does not match or oneshot raises
    proc3 = MockProc(103, "other_proc.exe")
    proc4 = MockProc(104, exe_name, raises_in_oneshot=True)
    with (
        patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True),
        patch("psutil.process_iter", return_value=[proc3, proc4]),
    ):
        assert find_untracked_server_process(server_dir) is None


async def test_untracked_scan_throttling(tmp_path: Path):
    """Test that untracked process scans are throttled when a server is stopped."""
    server_dir = str(tmp_path / "server")
    config_dir = str(tmp_path / "config")
    os.makedirs(server_dir, exist_ok=True)
    os.makedirs(
        os.path.join(config_dir, "runtime", "servers", "test_srv"), exist_ok=True
    )

    clear_untracked_scan_cache()

    with patch(
        "bedrock_server_manager.core.system.process.find_untracked_server_process",
        return_value=None,
    ) as mock_scan:
        res1 = await get_verified_bedrock_process("test_srv", server_dir, config_dir)
        assert res1 is None
        assert mock_scan.call_count == 1

        # Second call immediately after should be throttled
        res2 = await get_verified_bedrock_process("test_srv", server_dir, config_dir)
        assert res2 is None
        assert mock_scan.call_count == 1

        # Clearing cache allows scanning again
        clear_untracked_scan_cache()
        res3 = await get_verified_bedrock_process("test_srv", server_dir, config_dir)
        assert res3 is None
        assert mock_scan.call_count == 2
