"""Private, capture-local sequential copies of staged file contents."""

from pathlib import Path
from typing import BinaryIO

from ..utils.threads import run_in_thread


class CaptureSpool:
    """Keep one open file during sequential capture; never persist its index."""

    def __init__(self, path: Path):
        self.path = path
        self.entries: dict[Path, tuple[int, int, int]] = {}
        self.stream: BinaryIO | None = None

    def __enter__(self):
        self.stream = self.path.open("x+b")
        return self

    def __exit__(self, *args):
        if self.stream is not None:
            self.stream.close()

    async def __aenter__(self):
        return await run_in_thread(self.__enter__)

    async def __aexit__(self, *args):
        await run_in_thread(self.__exit__, *args)

    def flush(self) -> None:
        assert self.stream is not None
        self.stream.flush()

    def offset(self, source: Path) -> int | None:
        entry = self.entries.get(source)
        if entry is None:
            return None
        metadata = source.stat()
        size, modified, offset = entry
        return (
            offset
            if (metadata.st_size, metadata.st_mtime_ns) == (size, modified)
            else None
        )
