import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from bedrock_server_manager.context import AppContext
from bedrock_server_manager.error import (
    AppFileNotFoundError,
    ConfigurationError,
    FileOperationError,
    InvalidServerNameError,
    MissingArgumentError,
)

logger = logging.getLogger(__name__)


class DiscoveryMixin:
    """
    Mixin class for BedrockServerManager that handles server discovery and validation.
    """

    def validate_server(self, server_name: str, app_context: "AppContext") -> bool:
        """Validates if a given server name corresponds to a valid installation.

        This method checks for the existence and basic integrity of a server
        installation. It instantiates a :class:`~.core.bedrock_server.BedrockServer`
        object for the given ``server_name`` and then calls its
        :meth:`~.core.bedrock_server.BedrockServer.is_installed` method.

        Any exceptions raised during the instantiation or validation process (e.g.,
        :class:`~.error.InvalidServerNameError`, :class:`~.error.ConfigurationError`)
        are caught, logged as a warning, and result in a ``False`` return value,
        making this a safe check.

        Args:
            server_name (str): The name of the server to validate. This should
                correspond to a subdirectory within the main server base directory.

        Returns:
            bool: ``True`` if the server exists and is a valid installation
            (i.e., its directory and executable are found), ``False`` otherwise.

        Raises:
            MissingArgumentError: If ``server_name`` is an empty string.
        """
        if not server_name:
            raise MissingArgumentError("Server name cannot be empty for validation.")

        logger.debug(
            f"BSM: Validating server '{server_name}' using BedrockServer class."
        )
        try:
            server_instance = app_context.get_server(server_name)
            is_valid = server_instance.is_installed()
            if is_valid:
                logger.debug(f"BSM: Server '{server_name}' validation successful.")
            else:
                logger.debug(
                    f"BSM: Server '{server_name}' validation failed (directory or executable missing)."
                )
            return is_valid
        except (
            ValueError,
            MissingArgumentError,
            ConfigurationError,
            InvalidServerNameError,
            Exception,
        ) as e_val:
            # Treat any error during instantiation or validation as a failure.
            logger.warning(
                f"BSM: Validation failed for server '{server_name}' due to an error: {e_val}"
            )
            return False

    def get_servers_data(
        self, app_context: "AppContext"
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Discovers and retrieves status data for all valid server instances.

        This method scans the main server base directory (defined by
        ``settings['paths.servers']``) for subdirectories that represent server
        installations. For each potential server, it:

            1. Instantiates a :class:`~.core.bedrock_server.BedrockServer` object.
            2. Validates the installation using the server's :meth:`~.core.bedrock_server.BedrockServer.is_installed` method.
            3. If valid, it queries the server's status and version using
               :meth:`~.core.bedrock_server.BedrockServer.get_status` and
               :meth:`~.core.bedrock_server.BedrockServer.get_version`.

        Errors encountered while processing individual servers are collected and
        returned separately, allowing the method to succeed even if some server
        directories are corrupted or misconfigured. The final list of server
        data is sorted alphabetically by server name.

        Returns:
            Tuple[List[Dict[str, Any]], List[str]]: A tuple containing two lists:

                - The first list contains dictionaries, one for each successfully
                  processed server. Each dictionary has the keys:

                    - ``"name"`` (str): The name of the server.
                    - ``"status"`` (str): The server's current status (e.g., "RUNNING", "STOPPED").
                    - ``"version"`` (str): The detected version of the server.

                - The second list contains string messages describing any errors that
                  occurred while processing specific server candidates.

        Raises:
            AppFileNotFoundError: If the main server base directory
                (``settings['paths.servers']``) is not configured or does not exist.
        """
        servers_data: List[Dict[str, Any]] = []
        error_messages: List[str] = []

        if not self._base_dir or not os.path.isdir(self._base_dir):
            raise AppFileNotFoundError(str(self._base_dir), "Server base directory")

        for server_name_candidate in os.listdir(self._base_dir):
            potential_server_path = os.path.join(self._base_dir, server_name_candidate)
            if not os.path.isdir(potential_server_path):
                continue

            try:

                server = app_context.get_server(server_name_candidate)

                # Use the instance's own method to validate its installation.
                if not server.is_installed():
                    logger.debug(
                        f"Skipping '{server_name_candidate}': Not a valid server installation."
                    )
                    continue

                # Use the instance's methods to get its current state.
                status = server.get_status()
                version = server.get_version()
                servers_data.append(
                    {
                        "name": server.server_name,
                        "status": status,
                        "version": version,
                        "player_count": server.player_count,
                    }
                )

            except (
                FileOperationError,
                ConfigurationError,
                InvalidServerNameError,
            ) as e:
                msg = f"Could not get info for server '{server_name_candidate}': {e}"
                logger.warning(msg)
                error_messages.append(msg)
            except Exception as e:
                msg = f"An unexpected error occurred while processing server '{server_name_candidate}': {e}"
                logger.error(msg, exc_info=True)
                error_messages.append(msg)

        # Sort the final list alphabetically by server name for consistent output.
        servers_data.sort(key=lambda s: s.get("name", "").lower())
        return servers_data, error_messages
