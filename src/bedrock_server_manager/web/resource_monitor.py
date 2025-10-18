# bedrock_server_manager/web/resource_monitor.py
import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..context import AppContext

from ..api import system as system_api

logger = logging.getLogger(__name__)


class ResourceMonitor:
    """
    A background task that periodically gathers and broadcasts resource usage
    for servers that have active WebSocket subscribers.
    """

    def __init__(self, app_context: "AppContext"):
        """
        Initializes the ResourceMonitor.

        Args:
            app_context: The global application context.
        """
        self.app_context = app_context
        self._task: asyncio.Task | None = None

    async def _monitor_loop(self):
        """
        The main loop that continuously checks for subscriptions and broadcasts data.
        """
        while True:
            try:
                connection_manager = self.app_context.connection_manager
                # Get a copy of topics to avoid issues with concurrent modifications
                topics = list(connection_manager.subscriptions.keys())

                for topic in topics:
                    if topic.startswith("resource-monitor:"):
                        # Check if anyone is actually subscribed to this topic
                        if not connection_manager.subscriptions.get(topic):
                            continue

                        server_name = topic.split(":", 1)[1]
                        if server_name:
                            # Run the synchronous, blocking call in a separate thread
                            process_info = await asyncio.to_thread(
                                system_api.get_bedrock_process_info,
                                server_name=server_name,
                                app_context=self.app_context,
                            )
                            message = {
                                "type": "resource_update",
                                "topic": topic,
                                "data": process_info,
                            }
                            await connection_manager.broadcast_to_topic(topic, message)
            except Exception as e:
                logger.error(f"Error in resource monitor loop: {e}", exc_info=True)

            await asyncio.sleep(2)  # Broadcast every 2 seconds

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
