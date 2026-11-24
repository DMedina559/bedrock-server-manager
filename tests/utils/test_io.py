import asyncio
import threading
import time
from pathlib import Path

import pytest

from bedrock_server_manager.utils import io
from bedrock_server_manager.utils.io import load_json, load_lines, save_json, save_lines


async def test_atomic_save_round_trip_concurrent_and_failure_preservation(
    tmp_path, monkeypatch
):
    for kind in ("json", "lines"):
        path = tmp_path / "nested" / f"round_trip.{kind}"
        save, load = (
            (save_json, load_json) if kind == "json" else (save_lines, load_lines)
        )
        data = (
            {"key": "value", "unicode": "café", "list": [1, 2, 3]}
            if kind == "json"
            else ["line 1\n", "café\n"]
        )
        await save(data, str(path))
        assert await load(str(path)) == data
        assert not list(path.parent.glob("*.tmp"))

        # Concurrent writers
        c_path = tmp_path / f"concurrent.{kind}"
        candidates = [
            (
                {"writer": i, "payload": str(i) * 1000}
                if kind == "json"
                else [f"writer {i}\n", f"payload {i}\n"]
            )
            for i in range(25)
        ]
        await asyncio.gather(*(save(d, str(c_path)) for d in candidates))
        assert await load(str(c_path)) in candidates
        assert not list(tmp_path.glob("*.tmp"))

        # Failure preservation (serialization & replacement)
        f_path = tmp_path / f"original.{kind}"
        original = {"state": "original"} if kind == "json" else ["original\n"]
        replacement = {"state": "replacement"} if kind == "json" else ["replacement\n"]
        await save(original, str(f_path))
        original_bytes = f_path.read_bytes()

        invalid = {"invalid": object()} if kind == "json" else [object()]
        with pytest.raises(TypeError):
            await save(invalid, str(f_path))
        assert f_path.read_bytes() == original_bytes

        observed = []

        def fail_replace(
            source, target, orig_b=original_bytes, f_p=f_path, obs=observed
        ):
            temporary = Path(source)
            assert temporary.is_file() and temporary.read_bytes()
            assert f_p.read_bytes() == orig_b
            obs.append(temporary)
            raise OSError("Injected atomic replacement failure")

        with monkeypatch.context() as fault:
            fault.setattr("bedrock_server_manager.utils.io.os.replace", fail_replace)
            with pytest.raises(OSError, match="Injected atomic replacement failure"):
                await save(replacement, str(f_path))
        assert len(observed) == 1 and not observed[0].exists()
        assert f_path.read_bytes() == original_bytes
        assert await load(str(f_path)) == original
        assert not list(tmp_path.glob("*.tmp"))
        await save(replacement, str(f_path))
        assert await load(str(f_path)) == replacement


async def test_atomic_save_windows_sharing_retries_and_serialization(
    tmp_path, monkeypatch
):
    replace = io.os.replace

    for kind in ("json", "lines"):
        save, load = (
            (save_json, load_json) if kind == "json" else (save_lines, load_lines)
        )
        original = {"state": "original"} if kind == "json" else ["original\n"]
        replacement = {"state": "replacement"} if kind == "json" else ["replacement\n"]

        for winerror in (5, 32, 33):
            path = tmp_path / f"sharing_{winerror}.{kind}"
            await save(original, str(path))
            attempts = []

            def sharing_conflict(source, target, att=attempts, we=winerror):
                att.append(source)
                if len(att) < 3:
                    error = PermissionError("Windows sharing conflict")
                    error.winerror = we
                    raise error
                replace(source, target)

            with monkeypatch.context() as fault:
                fault.setattr(io.os, "replace", sharing_conflict)
                fault.setattr(io.time, "sleep", lambda delay: None)
                await save(replacement, str(path))
            assert len(attempts) == 3
            assert await load(str(path)) == replacement
            assert not list(tmp_path.glob("*.tmp"))

        # Serializes competing replacements
        s_path = tmp_path / f"serialized.{kind}"
        candidates = [
            {"writer": index} if kind == "json" else [f"{index}\n"]
            for index in range(25)
        ]
        replacing = threading.Lock()
        overlaps = []

        def exclusive_replace(source, target, rep=replacing, ov=overlaps):
            if not rep.acquire(blocking=False):
                ov.append(source)
                error = PermissionError("Concurrent replacement")
                error.winerror = 5
                raise error
            try:
                time.sleep(0.002)
                replace(source, target)
            finally:
                rep.release()

        with monkeypatch.context() as fault:
            fault.setattr(io.os, "replace", exclusive_replace)
            await asyncio.gather(*(save(data, str(s_path)) for data in candidates))
        assert not overlaps
        assert await load(str(s_path)) in candidates
        assert not list(tmp_path.glob("*.tmp"))

    # Exhausted sharing retry preserves original
    locked_path = tmp_path / "locked.json"
    await save_json({"state": "original"}, str(locked_path))
    orig_locked = locked_path.read_bytes()
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
            await save_json({"state": "replacement"}, str(locked_path))
    assert len(attempts) == 8
    assert locked_path.read_bytes() == orig_locked
    assert not list(tmp_path.glob("*.tmp"))
