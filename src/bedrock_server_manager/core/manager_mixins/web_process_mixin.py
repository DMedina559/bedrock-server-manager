import logging
import os
from typing import List, Optional, Union

from bedrock_server_manager.context import AppContext
from bedrock_server_manager.error import ConfigurationError

logger = logging.getLogger(__name__)


class WebProcessMixin:
    """
    Mixin class for BedrockServerManager that handles direct Web UI process management.
    """

    def start_web_ui_direct(
        self,
        app_context: AppContext,
        host: Optional[Union[str, List[str]]] = None,
        debug: bool = False,
        threads: Optional[int] = None,
    ) -> None:
        """Starts the Web UI application directly in the current process (blocking).

        This method is intended for scenarios where the Web UI is launched with
        the ``--mode direct`` command-line argument. It dynamically imports and
        calls the :func:`~.web.app.run_web_server` function, which in turn
        starts the Uvicorn server hosting the FastAPI application.

        .. note::
            This is a blocking call and will occupy the current process until the
            web server is shut down.

        Args:
            host (Optional[Union[str, List[str]]]): The host address or list of
                addresses for the web server to bind to. Passed directly to
                :func:`~.web.app.run_web_server`. Defaults to ``None``.
            debug (bool): If ``True``, runs the underlying Uvicorn/FastAPI app
                in debug mode (e.g., with auto-reload). Passed directly to
                :func:`~.web.app.run_web_server`. Defaults to ``False``.
            threads (Optional[int]): Specifies the number of worker processes for Uvicorn

                Only used for Windows Service

        Raises:
            RuntimeError: If :func:`~.web.app.run_web_server` raises a RuntimeError
                (e.g., missing authentication environment variables).
            ImportError: If the web application components (e.g.,
                :func:`~.web.app.run_web_server`) cannot be imported.
            Exception: Re-raises other exceptions from :func:`~.web.app.run_web_server`
                if Uvicorn fails to start.
        """
        logger.info("BSM: Starting web application in direct mode (blocking)...")
        if not app_context:
            raise ConfigurationError(
                "AppContext is required to start the Web UI in direct mode."
            )
        try:
            from bedrock_server_manager.web.main import (
                run_web_server as run_bsm_web_application,
            )

            run_bsm_web_application(app_context, host, debug, threads)
            logger.info("BSM: Web application (direct mode) shut down.")
        except (RuntimeError, ImportError) as e:
            logger.critical(
                f"BSM: Failed to start web application directly: {e}", exc_info=True
            )
            raise

    def get_web_ui_pid_path(self) -> str:
        """Returns the absolute path to the PID file for the detached Web UI server.

        The PID file is typically stored in the application's configuration directory
        (:attr:`._config_dir`) with the filename defined by
        :attr:`._WEB_SERVER_PID_FILENAME`.

        Returns:
            str: The absolute path to the Web UI's PID file.
        """
        return os.path.join(self._config_dir, self._WEB_SERVER_PID_FILENAME)

    def get_web_ui_expected_start_arg(self) -> List[str]:
        """Returns the list of arguments used to identify a detached Web UI server process.

        These arguments (defined by :attr:`._WEB_SERVER_START_ARG`) are typically
        used by process management utilities to find and identify the correct
        Web UI server process when it's run in a detached or background mode.

        Returns:
            List[str]: A list of command-line arguments.
        """
        return self._WEB_SERVER_START_ARG

    def get_web_ui_executable_path(self) -> str:
        """Returns the path to the main application executable used for starting the Web UI.

        This path, stored in :attr:`._expath`, is essential for constructing
        commands to start the Web UI, especially for system services.

        Returns:
            str: The path to the application executable.

        Raises:
            ConfigurationError: If the application executable path (:attr:`._expath`)
                is not configured or is empty.
        """
        if not self._expath:
            raise ConfigurationError(
                "Application executable path (_expath) is not configured."
            )
        return self._expath
