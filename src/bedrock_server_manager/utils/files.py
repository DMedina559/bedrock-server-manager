"""Cancellation-owned temporary directories without event-loop filesystem work."""

import shutil
import tempfile
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
            try:
                await run_in_thread(shutil.rmtree, directory)
            except BaseException as cleanup_error:
                if original is None:
                    raise
                original.add_note(
                    f"Temporary directory cleanup also failed: {type(cleanup_error).__name__}"
                )
