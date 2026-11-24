"""Tests for system process management utilities in bedrock_server_manager.core.system.process."""

import asyncio
import os
from pathlib import Path
from unittest.mock import patch

import psutil
import pytest

from bedrock_server_manager.config import GUARD_VARIABLE
from bedrock_server_manager.core.system.process import (
    GuardedProcess,
    ProcessRecoveryState,
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
        with pytest.raises(SystemError):
            await get_verified_bedrock_process("myserver", "/server/dir", "/config")

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

    with pytest.raises(MissingArgumentError):
        await get_verified_bedrock_process("", "/server/dir", "/config")
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

        def status(self):
            return psutil.STATUS_RUNNING

        def exe(self):
            if isinstance(self._exe, Exception):
                raise self._exe
            return self._exe

    # A partial CWD match must not hide the later fully verified candidate.
    proc1 = MockProc(101, exe_name, cwd_val=server_dir, exe_val="/some/other/exe")
    with (
        patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True),
        patch("psutil.process_iter", return_value=[proc1]),
    ):
        assert find_untracked_server_process(server_dir) is None

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
        with pytest.raises(PermissionsError):
            find_untracked_server_process(server_dir)

    valid = MockProc(105, exe_name, cwd_val=server_dir, exe_val=exe_path)
    with patch("psutil.process_iter", return_value=[proc1, valid]):
        assert find_untracked_server_process(server_dir) == 105
    duplicate = MockProc(106, exe_name, cwd_val=server_dir, exe_val=exe_path)
    with patch("psutil.process_iter", return_value=[valid, duplicate]):
        with pytest.raises(ServerProcessError, match="Multiple Bedrock"):
            find_untracked_server_process(server_dir)

    # Case 3: Name does not match or oneshot raises
    proc3 = MockProc(103, "other_proc.exe")
    proc4 = MockProc(104, exe_name, raises_in_oneshot=True)
    with (
        patch("bedrock_server_manager.core.system.process.PSUTIL_AVAILABLE", True),
        patch("psutil.process_iter", return_value=[proc3, proc4]),
    ):
        assert find_untracked_server_process(server_dir) is None


async def test_untracked_discovery_concurrency_and_cache(tmp_path, monkeypatch):
    from bedrock_server_manager.core.system import process as module

    server_dir = tmp_path / "server"
    config_dir = tmp_path / "config"
    server_dir.mkdir()
    config_dir.mkdir()
    state = ProcessRecoveryState()
    original_thread = module.run_in_thread
    started, release = asyncio.Event(), asyncio.Event()
    scans = 0

    def discover(_):
        nonlocal scans
        scans += 1
        return psutil.Process().pid

    async def pause(fn, *args):
        if fn is module.find_untracked_server_process:
            started.set()
            await release.wait()
        return await original_thread(fn, *args)

    monkeypatch.setattr(module, "find_untracked_server_process", discover)
    monkeypatch.setattr(module, "run_in_thread", pause)

    async def verify(*args, **kwargs):
        return None

    monkeypatch.setattr(module, "verify_process_identity", verify)

    async def probe(**kwargs):
        return await get_verified_bedrock_process(
            "test", str(server_dir), str(config_dir), recovery_state=state, **kwargs
        )

    first = asyncio.create_task(probe())
    await asyncio.wait_for(started.wait(), 5)
    second = asyncio.create_task(probe())
    await asyncio.sleep(0)
    assert not second.done()
    second.cancel()
    await asyncio.gather(second, return_exceptions=True)
    third = asyncio.create_task(probe())
    release.set()
    one, three = await asyncio.gather(first, third)
    assert one.pid == three.pid == psutil.Process().pid
    assert scans == 1
    assert state.recovered_pids

    # Only a completed negative scan is cached; lifecycle calls force a fresh scan.
    pid_file = await get_bedrock_server_pid_file_path("test", str(config_dir))
    os.remove(pid_file)
    os.remove(pid_file + ".json")
    monkeypatch.setattr(module, "find_untracked_server_process", lambda _: None)
    assert await probe() is None
    assert state.last_negative_scan
    monkeypatch.setattr(module, "find_untracked_server_process", discover)
    assert await probe() is None
    assert (await probe(force_scan=True)).pid == psutil.Process().pid
    assert scans == 2


async def test_recovery_verification_and_write_failures_publish_nothing(
    tmp_path, monkeypatch
):
    from bedrock_server_manager.core.system import process as module
    from bedrock_server_manager.error import FileOperationError

    state = ProcessRecoveryState()
    monkeypatch.setattr(
        module, "find_untracked_server_process", lambda _: psutil.Process().pid
    )

    async def reject(*args, **kwargs):
        raise ServerProcessError("mismatch")

    monkeypatch.setattr(module, "verify_process_identity", reject)
    with pytest.raises(ServerProcessError, match="mismatch"):
        await get_verified_bedrock_process(
            "test", str(tmp_path), str(tmp_path), recovery_state=state
        )
    pid_file = tmp_path / "runtime" / "servers" / "test" / "bedrock_test.pid"
    assert not pid_file.exists()
    assert not state.recovered_pids

    async def verify(*args, **kwargs):
        return None

    async def fail_write(*args):
        raise FileOperationError("disk full")

    monkeypatch.setattr(module, "verify_process_identity", verify)
    monkeypatch.setattr(module, "write_pid_to_file", fail_write)
    with pytest.raises(FileOperationError, match="disk full"):
        await get_verified_bedrock_process(
            "test", str(tmp_path), str(tmp_path), recovery_state=state
        )
    assert not state.recovered_pids


async def test_recovery_cache_is_scoped_and_can_be_disabled(tmp_path, monkeypatch):
    from bedrock_server_manager.core.system import process as module

    state = ProcessRecoveryState()
    with patch.object(
        module, "find_untracked_server_process", return_value=None
    ) as scan:

        async def probe(root, **kwargs):
            root.mkdir(exist_ok=True)
            return await get_verified_bedrock_process(
                "same_name", str(root), str(root), recovery_state=state, **kwargs
            )

        assert await probe(tmp_path / "one") is None
        assert await probe(tmp_path / "one") is None
        assert scan.call_count == 1
        assert await probe(tmp_path / "two") is None
        assert scan.call_count == 2
        assert await probe(tmp_path / "three", recover_untracked=False) is None
        assert scan.call_count == 2
        other_state = ProcessRecoveryState()
        await get_verified_bedrock_process(
            "same_name",
            str(tmp_path / "one"),
            str(tmp_path / "one"),
            recovery_state=other_state,
        )
        assert scan.call_count == 3
