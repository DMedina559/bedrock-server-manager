import asyncio
from pathlib import Path

import pytest

from bedrock_server_manager.utils.io import load_json, load_lines, save_json, save_lines


@pytest.mark.parametrize("kind", ["json", "lines"])
async def test_atomic_save_round_trip(tmp_path, kind):
    path = tmp_path / "nested" / f"round_trip.{kind}"
    save, load = (save_json, load_json) if kind == "json" else (save_lines, load_lines)
    data = (
        {"key": "value", "unicode": "café", "list": [1, 2, 3]}
        if kind == "json"
        else ["line 1\n", "café\n"]
    )
    await save(data, str(path))
    assert await load(str(path)) == data
    assert not list(path.parent.glob("*.tmp"))


@pytest.mark.parametrize("kind", ["json", "lines"])
async def test_atomic_save_concurrent_writers_leave_one_complete_result(tmp_path, kind):
    path = tmp_path / f"concurrent.{kind}"
    save, load = (save_json, load_json) if kind == "json" else (save_lines, load_lines)
    candidates = [
        (
            {"writer": i, "payload": str(i) * 1000}
            if kind == "json"
            else [f"writer {i}\n", f"payload {i}\n"]
        )
        for i in range(50)
    ]
    # Unique temporary files and atomic replacement must protect concurrent callers.
    await asyncio.gather(*(save(data, str(path)) for data in candidates))
    assert await load(str(path)) in candidates
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("kind", ["json", "lines"])
@pytest.mark.parametrize("failure", ["serialization", "replacement"])
async def test_atomic_save_failure_preserves_original_and_removes_temporary_file(
    tmp_path, monkeypatch, kind, failure
):
    path = tmp_path / f"original.{kind}"
    save, load = (save_json, load_json) if kind == "json" else (save_lines, load_lines)
    original = {"state": "original"} if kind == "json" else ["original\n"]
    replacement = {"state": "replacement"} if kind == "json" else ["replacement\n"]
    await save(original, str(path))
    original_bytes = path.read_bytes()
    if failure == "serialization":
        invalid = {"invalid": object()} if kind == "json" else [object()]
        with pytest.raises(TypeError):
            await save(invalid, str(path))
    else:
        observed = []

        def fail_replace(source, target):
            temporary = Path(source)
            assert temporary.is_file()
            assert temporary.read_bytes()
            assert path.read_bytes() == original_bytes
            observed.append(temporary)
            raise OSError("Injected atomic replacement failure")

        with monkeypatch.context() as fault:
            fault.setattr("bedrock_server_manager.utils.io.os.replace", fail_replace)
            with pytest.raises(OSError, match="Injected atomic replacement failure"):
                await save(replacement, str(path))
        assert len(observed) == 1
        assert not observed[0].exists()
    assert path.read_bytes() == original_bytes
    assert await load(str(path)) == original
    assert not list(tmp_path.glob("*.tmp"))
    await save(replacement, str(path))
    assert await load(str(path)) == replacement


@pytest.mark.parametrize("kind", ["json", "lines"])
@pytest.mark.parametrize("winerror", [5, 32, 33])
async def test_atomic_save_retries_windows_sharing_conflicts(
    tmp_path, monkeypatch, kind, winerror
):
    from bedrock_server_manager.utils import io

    path = tmp_path / f"sharing.{kind}"
    save, load = (save_json, load_json) if kind == "json" else (save_lines, load_lines)
    original = {"state": "original"} if kind == "json" else ["original\n"]
    replacement = {"state": "replacement"} if kind == "json" else ["replacement\n"]
    await save(original, str(path))
    replace = io.os.replace
    attempts = []

    def sharing_conflict(source, target):
        attempts.append(source)
        if len(attempts) < 3:
            error = PermissionError("Windows sharing conflict")
            error.winerror = winerror
            raise error
        replace(source, target)

    with monkeypatch.context() as fault:
        fault.setattr(io.os, "replace", sharing_conflict)
        fault.setattr(io.time, "sleep", lambda delay: None)
        await save(replacement, str(path))
    assert len(attempts) == 3
    assert await load(str(path)) == replacement
    assert not list(tmp_path.glob("*.tmp"))


async def test_atomic_save_exhausted_sharing_retry_preserves_original(
    tmp_path, monkeypatch
):
    from bedrock_server_manager.utils import io

    path = tmp_path / "locked.json"
    await save_json({"state": "original"}, str(path))
    original = path.read_bytes()
    attempts = []

    def still_locked(source, target):
        attempts.append(source)
        error = PermissionError("Windows sharing conflict")
        error.winerror = 32
        raise error

    with monkeypatch.context() as fault:
        fault.setattr(io.os, "replace", still_locked)
        fault.setattr(io.time, "sleep", lambda delay: None)
        with pytest.raises(PermissionError):
            await save_json({"state": "replacement"}, str(path))
    assert len(attempts) == 8
    assert path.read_bytes() == original
    assert not list(tmp_path.glob("*.tmp"))
