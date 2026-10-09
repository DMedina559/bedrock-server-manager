# bedrock_server_manager/web/resource_monitor.py
import asyncio
import logging
from typing import TYPE_CHECKING, Callable

from .websocket_manager import ConnectionManager

if TYPE_CHECKING:
    from ..core.bedrock_server import BedrockServer

logger = logging.getLogger(__name__)


class ResourceMonitor:
    """
    A background task that periodically gathers and broadcasts resource usage
    for servers that have active WebSocket subscribers.
    """

    def __init__(
        self,
        connection_manager: ConnectionManager,
        server_provider: Callable[[str], "BedrockServer"] | None = None,
    ):
        """
        Initializes the ResourceMonitor with explicit dependencies.

        Args:
            connection_manager: The WebSocket connection manager.
            server_provider: Optional callable returning a BedrockServer instance by name.
        """
        self.connection_manager = connection_manager
        self.server_provider = server_provider
        self._task: asyncio.Task | None = None

    async def _monitor_loop(self):
        """
        The main loop that continuously checks for subscriptions and broadcasts data.
        """
        while True:
            try:
                connection_manager = self.connection_manager
                # Get a copy of topics to avoid issues with concurrent modifications
                topics = list(connection_manager.subscriptions.keys())

                for topic in topics:
                    if topic.startswith("resource-monitor:"):
                        # Check if anyone is actually subscribed to this topic
                        if not connection_manager.subscriptions.get(topic):
                            continue

                        server_name = topic.split(":", 1)[1]
                        if server_name and callable(self.server_provider):
                            server = self.server_provider(server_name)
                            if server:
                                process_info = await server.get_process_info()
                                message = {
                                    "type": "resource_update",
                                    "topic": topic,
                                    "data": {
                                        "status": "success",
                                        "process_info": process_info,
                                    },
                                }
                                await connection_manager.broadcast_to_topic(
                                    topic, message
                                )
            except Exception as e:
                logger.error(f"Error in resource monitor loop: {e}", exc_info=True)

            await asyncio.sleep(3)  # Broadcast every 3 seconds

    def start(self):
        """Starts the background monitoring task."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._monitor_loop())
            logger.info("Resource monitor background task started.")

    def stop(self):
        """Stops the background monitoring task."""
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None
            logger.info("Resource monitor background task stopped.")

    async def shutdown(self) -> None:
        """Cancel and await the monitor before releasing its dependencies."""
        task = self._task
        self.stop()
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
