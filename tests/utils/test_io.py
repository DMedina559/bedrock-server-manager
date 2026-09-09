import asyncio
import os
import shutil
import tempfile
from unittest import mock

import pytest

from bedrock_server_manager.utils.io import async_load_json, async_save_json


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


@pytest.mark.asyncio
async def test_async_save_and_load_json(temp_dir):
    filepath = os.path.join(temp_dir, "test.json")
    data = {"key": "value", "list": [1, 2, 3]}

    await async_save_json(data, filepath)

    assert os.path.exists(filepath)
    assert not os.path.exists(filepath + ".tmp")

    loaded_data = await async_load_json(filepath)
    assert loaded_data == data


@pytest.mark.asyncio
async def test_async_save_json_concurrency(temp_dir):
    """
    Test 50 rapid concurrent saves to the same file.
    Note: To prevent file corruption, this should ideally be wrapped
    in an asyncio.Lock by the caller (as implemented in BaseServerMixin),
    but the atomic os.replace guarantees that even without a lock,
    the file won't end up half-written or corrupted in standard environments.
    """
    filepath = os.path.join(temp_dir, "concurrent.json")

    async def save_task(i):
        # Even though these race to write to the same .tmp file, the
        # final os.replace is atomic.
        data = {"count": i}
        await async_save_json(data, filepath)

    tasks = [save_task(i) for i in range(50)]
    await asyncio.gather(*tasks)

    # We just want to ensure it didn't crash and the file is valid JSON
    assert os.path.exists(filepath)
    loaded = await async_load_json(filepath)
    assert "count" in loaded


@pytest.mark.asyncio
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
    with mock.patch(
        "bedrock_server_manager.utils.io.open", side_effect=OSError("Disk failure")
    ):
        with pytest.raises(OSError, match="Disk failure"):
            await async_save_json(corrupt_data, filepath)

    # Verify original file is perfectly intact
    loaded = await async_load_json(filepath)
    assert loaded == original_data

    # Verify temp file was cleaned up (or never successfully created)
    assert not os.path.exists(filepath + ".tmp")
