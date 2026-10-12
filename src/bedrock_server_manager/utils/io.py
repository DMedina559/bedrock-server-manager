import json
import os
import threading
import time
import uuid
from typing import Any, List

from .threads import run_in_thread

# A fixed lock pool bounds memory while serializing replacements of the same path.
_replacement_locks = tuple(threading.Lock() for _ in range(64))


def _replace_file(source: str, target: str) -> None:
    """Serialize local writers and retry brief external Windows sharing conflicts."""
    key = os.path.normcase(os.path.realpath(target))
    lock = _replacement_locks[hash(key) % len(_replacement_locks)]
    with lock:
        for attempt in range(8):
            try:
                os.replace(source, target)
                return
            except PermissionError as error:
                if getattr(error, "winerror", None) not in {5, 32, 33} or attempt == 7:
                    raise
                time.sleep(min(0.005 * 2**attempt, 0.1))


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

        _replace_file(temp_filepath, filepath)
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


async def save_json(data: Any, filepath: str, indent: int = 4) -> None:
    """Non-blocking asynchronous entry point to save data to a JSON file safely."""
    await run_in_thread(_sync_atomic_json_dump, data, filepath, indent)


async def load_json(filepath: str) -> Any:
    """Non-blocking asynchronous entry point to read and parse a JSON file safely."""
    return await run_in_thread(_sync_json_load, filepath)


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

        _replace_file(temp_filepath, filepath)
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


async def save_lines(lines: List[str], filepath: str) -> None:
    """Non-blocking asynchronous entry point to save lines of text to a file safely."""
    await run_in_thread(_sync_atomic_lines_dump, lines, filepath)


async def load_lines(filepath: str) -> List[str]:
    """Non-blocking asynchronous entry point to read lines from a file safely."""
    return await run_in_thread(_sync_lines_load, filepath)
