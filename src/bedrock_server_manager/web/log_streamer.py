import asyncio
import codecs
import hashlib
import logging
import os
from typing import TYPE_CHECKING, Callable, Dict, Optional

import aiofiles
import aiofiles.ospath
from pydantic import BaseModel

from ..core.system import find_files
from ..logging import RepeatedFailureReporter, get_application_log_path
from .websocket_manager import ConnectionManager

if TYPE_CHECKING:
    from ..core.bedrock_server import BedrockServer

logger = logging.getLogger(__name__)


class LogHistoryPage(BaseModel):
    data: str
    start: int
    end: int
    file_id: str
    has_more: bool


class LogStreamer:
    """
    Manages streaming of log files to WebSocket clients.

    Continuously monitors active WebSocket subscriptions and tails the corresponding
    log files, broadcasting new lines to subscribed clients.
    """

    def __init__(
        self,
        connection_manager: ConnectionManager,
        log_dir: str,
        server_provider: Optional[Callable[[str], "BedrockServer"]] = None,
    ):
        self.connection_manager = connection_manager
        self.log_dir = log_dir
        self.server_provider = server_provider
        self.running = False
        self._task = None
        # Aliases may watch the same file, but each topic needs its own cursor.
        self.file_positions: Dict[tuple[str, str], int] = {}
        self._file_identities: Dict[tuple[str, str], tuple[int, int]] = {}
        self._decoders: Dict[tuple[str, str], codecs.IncrementalDecoder] = {}
        self._failures = RepeatedFailureReporter(logger)

    def start(self):
        """Starts the log streaming background task."""
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._stream_logs())
        logger.debug("LogStreamer started.")

    def stop(self):
        """Stops the log streaming background task."""
        self.running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.debug("LogStreamer stopped.")

    async def _stream_logs(self) -> None:  # noqa: C901
        """Main loop that checks subscriptions and streams log updates."""
        while self.running:
            try:
                # 1. Identify active log subscriptions
                subscriptions = self.connection_manager.subscriptions
                active_topics = subscriptions.keys()

                files_to_watch: Dict[str, str] = {}  # topic -> file_path

                # Check for app log subscription
                for topic in ("app_log", "app_logs"):
                    if topic in active_topics and subscriptions[topic]:
                        log_path = await self._get_app_log_path()
                        if log_path:
                            files_to_watch[topic] = log_path

                # Check for server log subscriptions
                # Topic format: server_log:{server_name}
                for topic in active_topics:
                    if topic.startswith("server_log:") and subscriptions[topic]:
                        server_name = topic.split(":", 1)[1]
                        server = (
                            self.server_provider(server_name)
                            if callable(self.server_provider)
                            else None
                        )
                        if server:
                            log_path = server.paths.server_log_path
                            if await aiofiles.ospath.exists(log_path):
                                files_to_watch[topic] = log_path

                # 2. Read and broadcast updates
                for topic, file_path in files_to_watch.items():
                    await self._process_file(topic, file_path)

                watched = set(files_to_watch.items())
                for key in list(self.file_positions):
                    if key not in watched:
                        self.file_positions.pop(key, None)
                        self._file_identities.pop(key, None)
                        self._decoders.pop(key, None)
                        self._failures.failures.pop(key[1], None)
                self._failures.recover("log streaming")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._failures.report(
                    "log streaming", "Log streaming unavailable (%s): %s; retrying.", e
                )

            await asyncio.sleep(1.0)  # Check every second

    async def _get_app_log_path(self) -> Optional[str]:
        log_dir = self.log_dir
        if not log_dir or not await aiofiles.ospath.isdir(log_dir):
            return None

        active_path = get_application_log_path(log_dir)
        if active_path and await aiofiles.ospath.exists(active_path):
            self._failures.recover("application log discovery")
            return active_path

        # Check for fixed filename first
        fixed_path = os.path.abspath(
            os.path.join(log_dir, "bedrock_server_manager.log")
        )
        if await aiofiles.ospath.exists(fixed_path):
            self._failures.recover("application log discovery")
            return fixed_path

        # Check for timestamped log files (e.g. bedrock_server_manager_20260924_012943.log)
        try:
            log_files = await find_files(
                log_dir, "bedrock_server_manager*.log", sort_by="mtime", reverse=True
            )
            if log_files:
                p = log_files[0]
                file_path = p if isinstance(p, str) else str(p.get("path", ""))
                if file_path and await aiofiles.ospath.exists(file_path):
                    self._failures.recover("application log discovery")
                    return os.path.abspath(file_path)
            self._failures.recover("application log discovery")
        except Exception as e:
            self._failures.report(
                "application log discovery", "Could not locate %s: %s; retrying.", e
            )

        return None

    async def _resolve_topic_path(self, topic: str) -> str | None:
        if topic in ("app_log", "app_logs"):
            return await self._get_app_log_path()
        if topic.startswith("server_log:") and callable(self.server_provider):
            server = self.server_provider(topic.split(":", 1)[1])
            if server is not None:
                return server.paths.server_log_path
        return None

    @staticmethod
    def _file_id(file_path: str, stat: os.stat_result) -> str:
        identity = f"{os.path.realpath(file_path)}:{stat.st_dev}:{stat.st_ino}"
        return hashlib.sha256(identity.encode()).hexdigest()

    async def read_history(
        self, topic: str, before: int | None = None, file_id: str | None = None
    ) -> LogHistoryPage:
        """Read a bounded page backwards without changing any live cursor."""
        path = await self._resolve_topic_path(topic)
        if not path:
            raise FileNotFoundError("Log is unavailable.")
        async with aiofiles.open(path, "rb") as file:
            stat = await asyncio.to_thread(os.fstat, file.fileno())
            identity = self._file_id(path, stat)
            if file_id is not None and file_id != identity:
                raise ValueError("Log file changed; reload the viewer.")
            end = stat.st_size if before is None else before
            if end < 0 or end > stat.st_size:
                raise ValueError("Log file changed; reload the viewer.")
            start = max(0, end - 64 * 1024)
            await file.seek(start)
            content = await file.read(end - start)
            # Page boundaries are UTF-8 boundaries so concatenated pages preserve
            # the complete file, including partial lines and blank lines.
            while content and start > 0 and content[0] & 0xC0 == 0x80:
                content = content[1:]
                start += 1
            decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
            text = decoder.decode(content)
            end -= len(decoder.getstate()[0])
            return LogHistoryPage(
                data=text,
                start=start,
                end=end,
                file_id=identity,
                has_more=start > 0,
            )

    async def _process_file(self, topic: str, file_path: str):
        """Reads new lines from a file and broadcasts them to a topic."""
        key = (topic, file_path)
        try:
            async with aiofiles.open(file_path, "rb") as file:
                stat = await asyncio.to_thread(os.fstat, file.fileno())
                identity = (stat.st_dev, stat.st_ino)
                initial = key not in self.file_positions
                replaced = self._file_identities.get(key) != identity
                current_pos = self.file_positions.get(key, max(0, stat.st_size - 2048))
                if initial or replaced or stat.st_size < current_pos:
                    current_pos = max(0, stat.st_size - 2048) if initial else 0
                    self._decoders[key] = codecs.getincrementaldecoder("utf-8")(
                        errors="replace"
                    )
                    await file.seek(current_pos)
                    if initial and current_pos:
                        # Start on a complete line, never halfway through UTF-8.
                        # Bound this read too, even for files containing one huge line.
                        fragment = await file.read(2048)
                        newline = fragment.find(b"\n")
                        current_pos += newline + 1 if newline >= 0 else len(fragment)
                await file.seek(current_pos)
                content = await file.read(64 * 1024)
                decoder = self._decoders[key]
                pending = len(decoder.getstate()[0])
                new_content = decoder.decode(content)
                end = await file.tell()
                self.file_positions[key] = end
                self._file_identities[key] = identity
                if new_content:
                    await self.connection_manager.broadcast_to_topic(
                        topic,
                        {
                            "type": "log_update",
                            "topic": topic,
                            "data": new_content,
                            "start": current_pos - pending,
                            "end": end - len(decoder.getstate()[0]),
                            "file_id": self._file_id(file_path, stat),
                        },
                    )
            self._failures.recover(file_path)

        except Exception as e:
            self._failures.report(
                file_path, "Could not stream log '%s': %s; retrying.", e
            )

    async def shutdown(self) -> None:
        """Cancel and await the monitor before releasing its dependencies."""
        task = self._task
        self.stop()
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
