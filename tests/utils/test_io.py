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
