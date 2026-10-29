"""Cancellation-owned temporary directories without event-loop filesystem work."""

import logging
import shutil
import tempfile
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from .threads import run_in_thread


@asynccontextmanager
async def temporary_directory(
    parent: str | Path | None = None, *, prefix: str = "bsm-"
) -> AsyncIterator[Path]:
    directory: Path | None = None
    original: BaseException | None = None

    def create() -> None:
        nonlocal directory
        directory = Path(tempfile.mkdtemp(prefix=prefix, dir=parent))

    try:
        await run_in_thread(create)
        assert directory is not None
        yield directory
    except BaseException as error:
        original = error
        raise
    finally:
        if directory is not None:
            started = time.monotonic()
            status = "failed"
            try:
                await run_in_thread(shutil.rmtree, directory)
                status = "completed"
            except BaseException as cleanup_error:
                if original is None:
                    raise
                original.add_note(
                    f"Temporary directory cleanup also failed: {type(cleanup_error).__name__}"
                )
            finally:
                logging.getLogger(__name__).debug(
                    "Temporary staging cleanup: status=%s duration_ms=%.3f",
                    status,
                    (time.monotonic() - started) * 1000,
                )
