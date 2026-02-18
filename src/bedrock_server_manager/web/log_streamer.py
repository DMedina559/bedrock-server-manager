import asyncio
import logging
import os
from typing import Dict

from ..context import AppContext

logger = logging.getLogger(__name__)


class LogStreamer:
    """
    Manages streaming of log files to WebSocket clients.

    Continuously monitors active WebSocket subscriptions and tails the corresponding
    log files, broadcasting new lines to subscribed clients.
    """

    def __init__(self, app_context: AppContext):
        self.app_context = app_context
        self.connection_manager = app_context.connection_manager
        self.running = False
        self._task = None
        # Maps file path to current file pointer position
        self.file_positions: Dict[str, int] = {}

    def start(self):
        """Starts the log streaming background task."""
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._stream_logs())
        logger.info("LogStreamer started.")

    def stop(self):
        """Stops the log streaming background task."""
        self.running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("LogStreamer stopped.")

    async def _stream_logs(self):  # noqa: C901
        """Main loop that checks subscriptions and streams log updates."""
        while self.running:
            try:
                # 1. Identify active log subscriptions
                subscriptions = self.connection_manager.subscriptions
                active_topics = subscriptions.keys()

                files_to_watch: Dict[str, str] = {}  # topic -> file_path

                # Check for app log subscription
                if "app_log" in active_topics and subscriptions["app_log"]:
                    log_path = os.path.abspath(
                        f"{self.app_context.settings.get('paths.logs')}/bedrock_server_manager.log"
                    )
                    if os.path.exists(log_path):
                        files_to_watch["app_log"] = log_path

                # Check for server log subscriptions
                # Topic format: server_log:{server_name}
                for topic in active_topics:
                    if topic.startswith("server_log:") and subscriptions[topic]:
                        server_name = topic.split(":", 1)[1]
                        server = self.app_context.get_server(server_name)
                        if server:
                            log_path = server.server_log_path
                            if os.path.exists(log_path):
                                files_to_watch[topic] = log_path

                # 2. Read and broadcast updates
                for topic, file_path in files_to_watch.items():
                    await self._process_file(topic, file_path)

                # Clean up file positions for files no longer being watched
                watched_paths = set(files_to_watch.values())
                tracked_paths = list(self.file_positions.keys())
                for path in tracked_paths:
                    if path not in watched_paths:
                        del self.file_positions[path]

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in LogStreamer loop: {e}")

            await asyncio.sleep(1.0)  # Check every second

    async def _process_file(self, topic: str, file_path: str):
        """Reads new lines from a file and broadcasts them to a topic."""
        try:
            if file_path not in self.file_positions:
                size = os.path.getsize(file_path)
                # If we want to show last ~1KB or so:
                start_pos = max(0, size - 2048)
                self.file_positions[file_path] = start_pos

            current_pos = self.file_positions[file_path]
            current_size = os.path.getsize(file_path)

            if current_size < current_pos:
                current_pos = 0
                self.file_positions[file_path] = 0

            if current_size > current_pos:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(current_pos)
                    # Read new content
                    new_content = f.read()
                    if new_content:
                        # Update position
                        self.file_positions[file_path] = f.tell()

                        # Broadcast lines
                        await self.connection_manager.broadcast_to_topic(
                            topic,
                            {"type": "log_update", "topic": topic, "data": new_content},
                        )

        except Exception as e:
            logger.warning(f"Failed to read log file {file_path}: {e}")
