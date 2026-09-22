import asyncio
import os
import shutil
import tempfile
from unittest import mock

import pytest

from bedrock_server_manager.utils.io import (
    async_load_json,
    async_load_lines,
    async_save_json,
    async_save_lines,
)


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


async def test_async_save_and_load_json(temp_dir):
    filepath = os.path.join(temp_dir, "test.json")
    data = {"key": "value", "list": [1, 2, 3]}

    await async_save_json(data, filepath)

    assert os.path.exists(filepath)
    assert not os.path.exists(filepath + ".tmp")

    loaded_data = await async_load_json(filepath)
    assert loaded_data == data


async def test_async_save_json_concurrency(temp_dir):
    """
    Test 50 rapid concurrent saves to the same file.
    Uses asyncio.Lock() to mimic real-world usage in BaseServerMixin
    and prevent Windows PermissionError (WinError 5) during os.replace.
    """
    filepath = os.path.join(temp_dir, "concurrent.json")
    lock = asyncio.Lock()

    async def save_task(i):
        data = {"count": i}
        # Safely acquire the lock before doing the file operation
        async with lock:
            await async_save_json(data, filepath)

    tasks = [save_task(i) for i in range(50)]
    await asyncio.gather(*tasks)

    # We just want to ensure it didn't crash and the file is valid JSON
    assert os.path.exists(filepath)
    loaded = await async_load_json(filepath)
    assert "count" in loaded


async def test_async_save_json_fault_tolerance(temp_dir):
    """
    Mock a failure during the JSON dump to ensure the original file
    is not overwritten and the tmp file is cleaned up.
    """
    filepath = os.path.join(temp_dir, "fault_test.json")
    original_data = {"status": "original"}

    # Write the initial valid file
    await async_save_json(original_data, filepath)

    corrupt_data = {"status": "corrupting"}

    # Force a failure during the open/dump phase
    with mock.patch("builtins.open", side_effect=OSError("Disk failure")):
        with pytest.raises(OSError, match="Disk failure"):
            await async_save_json(corrupt_data, filepath)

    # Verify original file is perfectly intact
    loaded = await async_load_json(filepath)
    assert loaded == original_data

    # Verify temp file was cleaned up (or never successfully created)
    assert not os.path.exists(filepath + ".tmp")


async def test_async_save_and_load_lines(temp_dir):
    filepath = os.path.join(temp_dir, "test.txt")
    lines = ["line 1\n", "line 2\n", "line 3\n"]

    await async_save_lines(lines, filepath)

    assert os.path.exists(filepath)

    loaded_lines = await async_load_lines(filepath)
    assert loaded_lines == lines


async def test_async_save_lines_concurrency(temp_dir):
    """
    Test 50 rapid concurrent line saves to the same file.
    Uses asyncio.Lock() to prevent Windows locking errors.
    """
    filepath = os.path.join(temp_dir, "concurrent_lines.txt")
    lock = asyncio.Lock()

    async def save_task(i):
        lines = [f"line {i}\n"]
        # Safely acquire the lock before doing the file operation
        async with lock:
            await async_save_lines(lines, filepath)

    tasks = [save_task(i) for i in range(50)]
    await asyncio.gather(*tasks)

    assert os.path.exists(filepath)
    loaded = await async_load_lines(filepath)
    assert len(loaded) == 1
    assert loaded[0].startswith("line ")


async def test_async_save_lines_fault_tolerance(temp_dir):
    filepath = os.path.join(temp_dir, "fault_test_lines.txt")
    original_lines = ["original\n"]

    await async_save_lines(original_lines, filepath)

    corrupt_lines = ["corrupting\n"]

    with mock.patch("builtins.open", side_effect=OSError("Disk failure")):
        with pytest.raises(OSError, match="Disk failure"):
            await async_save_lines(corrupt_lines, filepath)

    loaded = await async_load_lines(filepath)
    assert loaded == original_lines
