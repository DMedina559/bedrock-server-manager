import asyncio
import json
import os
import uuid
from typing import Any, List


def _sync_atomic_json_dump(data: Any, filepath: str, indent: int = 4) -> None:
    """
    Executes synchronously within a worker thread. Writes data to a
    temporary file and performs an atomic swap to prevent corruption.
    """
    # Append a unique ID to prevent temp file collision during heavy concurrency
    temp_filepath = f"{filepath}.{uuid.uuid4().hex}.tmp"
    try:
        # Guarantee directory existence
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        with open(temp_filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())  # Force OS buffer write to physical media

        os.replace(temp_filepath, filepath)
    except Exception as e:
        if os.path.exists(temp_filepath):
            try:
                os.remove(temp_filepath)
            except OSError:
                pass
        raise e


def _sync_json_load(filepath: str) -> Any:
    """Executes synchronously within a worker thread to safely parse JSON files."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Target JSON file not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


async def async_save_json(data: Any, filepath: str, indent: int = 4) -> None:
    """Non-blocking asynchronous entry point to save data to a JSON file safely."""
    await asyncio.to_thread(_sync_atomic_json_dump, data, filepath, indent)


async def async_load_json(filepath: str) -> Any:
    """Non-blocking asynchronous entry point to read and parse a JSON file safely."""
    return await asyncio.to_thread(_sync_json_load, filepath)


def _sync_atomic_lines_dump(lines: List[str], filepath: str) -> None:
    """
    Executes synchronously within a worker thread. Writes lines of text to a
    temporary file and performs an atomic swap to prevent corruption.
    """
    temp_filepath = f"{filepath}.{uuid.uuid4().hex}.tmp"
    try:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        with open(temp_filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_filepath, filepath)
    except Exception as e:
        if os.path.exists(temp_filepath):
            try:
                os.remove(temp_filepath)
            except OSError:
                pass
        raise e


def _sync_lines_load(filepath: str) -> List[str]:
    """Executes synchronously within a worker thread to safely read lines from a file."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Target file not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return f.readlines()


async def async_save_lines(lines: List[str], filepath: str) -> None:
    """Non-blocking asynchronous entry point to save lines of text to a file safely."""
    await asyncio.to_thread(_sync_atomic_lines_dump, lines, filepath)


async def async_load_lines(filepath: str) -> List[str]:
    """Non-blocking asynchronous entry point to read lines from a file safely."""
    return await asyncio.to_thread(_sync_lines_load, filepath)
