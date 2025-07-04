# bedrock_server_manager/core/server/windows_service_mixin.py
"""
Provides the :class:`.ServerWindowsServiceMixin` for the
:class:`~.core.bedrock_server.BedrockServer` class.

This mixin encapsulates all Windows-specific Service management for a Bedrock
server instance. It allows for the creation, configuration (enable/disable),
removal, and status checking of Windows Services designed to manage the Bedrock
server process. This facilitates running the server as a background service with
autostart capabilities on Windows.

The functionality primarily delegates to helper utilities in the
:mod:`~.core.system.windows` module, which interact with the Windows Service
Control Manager (SCM) via ``pywin32`` or the ``sc.exe`` command-line tool.

.. warning::
    Nearly all operations in this mixin require the application to be run with
    **Administrator privileges**. Failure to do so will likely result in
    :class:`~.error.PermissionsError` or other system errors.
"""
import os
import subprocess
from typing import Any

# Local application imports.
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.core.system import windows as system_windows_utils
from bedrock_server_manager.error import (
    SystemError,
    AppFileNotFoundError,
    BSMError,
)


class ServerWindowsServiceMixin(BedrockServerBaseMixin):
    """Manages a Windows Service for a Bedrock server instance (Windows-only).

    This mixin extends :class:`.BedrockServerBaseMixin` and provides methods
    to interact with the Windows Service Control Manager (SCM) for a service
    associated with this specific Bedrock server instance. It allows for creating,
    configuring (enabling/disabling), removing, and querying the status of the
    Windows Service.

    All service manipulation methods delegate to helper functions in
    :mod:`~.core.system.windows`, which in turn use ``pywin32`` or ``sc.exe``.

    .. warning::
        All public methods in this mixin that modify or query service state
        (e.g., create, enable, disable, remove, check status) **require
        Administrator privileges** to execute correctly. Operations may fail
        with a :class:`~.error.PermissionsError` if run without sufficient rights.

    Properties:
        windows_service_name (str): The internal name of the Windows service.
        windows_service_display_name (str): The user-friendly display name for the service.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initializes the ServerWindowsServiceMixin.

        Calls ``super().__init__(*args, **kwargs)`` to participate in cooperative
        multiple inheritance. It relies on attributes initialized by
        :class:`.BedrockServerBaseMixin` such as `server_name`, `server_dir` (for
        service working directory), `manager_expath` (path to the application
        script/executable used in service commands), and `os_type`.

        Args:
            *args (Any): Variable length argument list passed to `super()`.
            **kwargs (Any): Arbitrary keyword arguments passed to `super()`.
        """
        super().__init__(*args, **kwargs)
        # Attributes from BedrockServerBaseMixin are available.

    def _ensure_windows_for_service(self, operation_name: str) -> None:
        """Internal helper to verify the OS is Windows before a service operation.

        Logs an error and raises :class:`~.error.SystemError` if the current OS
        is not "Windows".

        Args:
            operation_name (str): The name of the Windows Service-related operation
                being attempted (e.g., "create_windows_service"). Used for logging.

        Raises:
            SystemError: If the current operating system (``self.os_type``) is not "Windows".
        """
        if self.os_type != "Windows":
            msg = f"Windows Service operation '{operation_name}' is only supported on Windows. Current OS: {self.os_type}"
            self.logger.error(msg)  # Log as error due to incorrect usage context
            raise SystemError(msg)

    @property
    def windows_service_name(self) -> str:
        """str: The internal (short) name for the Windows Service.

        Constructed as ``bedrock-<server_name>`` (e.g., "bedrock-MyServer").
        This name is used when interacting with ``schtasks`` or ``pywin32`` service functions.
        """
        return f"bedrock-{self.server_name}"

    @property
    def windows_service_display_name(self) -> str:
        """str: The user-friendly display name for the Windows Service.

        Constructed as "Bedrock Server (<server_name>)" (e.g., "Bedrock Server (MyServer)").
        This name is typically shown in the Windows Services management console.
        """
        return f"Bedrock Server ({self.server_name})"

    def check_windows_service_exists(self) -> bool:
        """Checks if the Windows Service for this server exists (Windows-only).

        Delegates to :func:`~.core.system.windows.check_service_exists`.

        .. warning:: Requires Administrator privileges for a reliable check.

        Returns:
            bool: ``True`` if the service exists, ``False`` otherwise or if not on Windows.

        Raises:
            SystemError: If called on a non-Windows system, or for unexpected SCM errors.
        """
        self._ensure_windows_for_service("check_windows_service_exists")
        return system_windows_utils.check_service_exists(self.windows_service_name)

    def create_windows_service(self) -> None:
        """Creates or updates the Windows Service for this server (Windows-only).

        Constructs the service command using :attr:`.BedrockServerBaseMixin.manager_expath`
        to call ``service _run-bedrock --server <server_name>``.
        Delegates to :func:`~.core.system.windows.create_windows_service`.

        .. warning:: Requires Administrator privileges.

        Raises:
            SystemError: If called on a non-Windows system, or if ``pywin32`` is
                         unavailable, or for SCM errors.
            AppFileNotFoundError: If :attr:`.BedrockServerBaseMixin.manager_expath` is not found.
            PermissionsError: If not run with Administrator privileges.
            MissingArgumentError: If required arguments for delegation are missing.
        """
        self._ensure_windows_for_service("create_windows_service")

        if not self.manager_expath or not os.path.isfile(self.manager_expath):
            raise AppFileNotFoundError(
                str(self.manager_expath),  # Ensure str for AppFileNotFoundError
                f"Manager executable path for server '{self.server_name}' Windows service not found or invalid.",
            )

        description = (
            f"Manages the Minecraft Bedrock Server instance named '{self.server_name}'."
        )
        # Command for the service: path_to_bsm.exe service _run-bedrock --server "ServerName"
        # manager_expath should ideally be quoted if it might contain spaces,
        # but schtasks/CreateService handles quoting of the full command string.
        # However, individual arguments containing spaces passed TO our script need quoting.
        command = f'"{self.manager_expath}" service _run-bedrock --server "{self.server_name}"'

        self.logger.info(
            f"Creating/updating Windows service '{self.windows_service_name}' for server '{self.server_name}' with command: {command}"
        )
        try:
            system_windows_utils.create_windows_service(
                service_name=self.windows_service_name,
                display_name=self.windows_service_display_name,
                description=description,
                command=command,
            )
            self.logger.info(
                f"Windows service '{self.windows_service_name}' created/updated successfully."
            )
        except BSMError:  # Re-raise known BSM errors
            self.logger.error(
                f"Failed to create/update Windows service '{self.windows_service_name}'.",
                exc_info=True,
            )
            raise
        except Exception as e_unexp:  # Wrap unexpected errors
            self.logger.error(
                f"Unexpected error creating/updating Windows service '{self.windows_service_name}': {e_unexp}",
                exc_info=True,
            )
            raise SystemError(
                f"Unexpected error during Windows service creation: {e_unexp}"
            ) from e_unexp

    def enable_windows_service(self) -> None:
        """Enables the Windows Service (sets start type to Automatic) (Windows-only).

        Delegates to :func:`~.core.system.windows.enable_windows_service`.

        .. warning:: Requires Administrator privileges.

        Raises:
            SystemError: If not on Windows, service not found, or other SCM errors.
            PermissionsError: If not run with Administrator privileges.
            MissingArgumentError: If the service name is invalid.
        """
        self._ensure_windows_for_service("enable_windows_service")
        self.logger.info(
            f"Enabling Windows service '{self.windows_service_name}' for server '{self.server_name}'."
        )
        try:
            system_windows_utils.enable_windows_service(self.windows_service_name)
            self.logger.info(
                f"Windows service '{self.windows_service_name}' enabled successfully."
            )
        except BSMError:  # Re-raise known BSM errors
            self.logger.error(
                f"Failed to enable Windows service '{self.windows_service_name}'.",
                exc_info=True,
            )
            raise
        except Exception as e_unexp:  # Wrap unexpected errors
            self.logger.error(
                f"Unexpected error enabling Windows service '{self.windows_service_name}': {e_unexp}",
                exc_info=True,
            )
            raise SystemError(
                f"Unexpected error during Windows service enable: {e_unexp}"
            ) from e_unexp

    def disable_windows_service(self) -> None:
        """Disables the Windows Service (sets start type to Disabled) (Windows-only).

        Delegates to :func:`~.core.system.windows.disable_windows_service`.

        .. warning:: Requires Administrator privileges.

        Raises:
            SystemError: If not on Windows or other SCM errors (service not found is handled gracefully).
            PermissionsError: If not run with Administrator privileges.
            MissingArgumentError: If the service name is invalid.
        """
        self._ensure_windows_for_service("disable_windows_service")
        self.logger.info(
            f"Disabling Windows service '{self.windows_service_name}' for server '{self.server_name}'."
        )
        try:
            system_windows_utils.disable_windows_service(self.windows_service_name)
            self.logger.info(
                f"Windows service '{self.windows_service_name}' disabled successfully."
            )
        except BSMError:  # Re-raise known BSM errors
            self.logger.error(
                f"Failed to disable Windows service '{self.windows_service_name}'.",
                exc_info=True,
            )
            raise
        except Exception as e_unexp:  # Wrap unexpected errors
            self.logger.error(
                f"Unexpected error disabling Windows service '{self.windows_service_name}': {e_unexp}",
                exc_info=True,
            )
            raise SystemError(
                f"Unexpected error during Windows service disable: {e_unexp}"
            ) from e_unexp

    def remove_windows_service(self) -> None:
        """Removes (deletes) the Windows Service for this server (Windows-only).

        Delegates to :func:`~.core.system.windows.delete_windows_service`.
        The service should ideally be stopped before deletion.

        .. warning:: Requires Administrator privileges.

        Raises:
            SystemError: If not on Windows or for critical SCM errors during deletion.
            PermissionsError: If not run with Administrator privileges.
            MissingArgumentError: If the service name is invalid.
        """
        self._ensure_windows_for_service("remove_windows_service")
        self.logger.info(
            f"Removing Windows service '{self.windows_service_name}' for server '{self.server_name}'."
        )
        try:
            system_windows_utils.delete_windows_service(self.windows_service_name)
            self.logger.info(
                f"Windows service '{self.windows_service_name}' removed successfully."
            )
        except BSMError:  # Re-raise known BSM errors
            self.logger.error(
                f"Failed to remove Windows service '{self.windows_service_name}'.",
                exc_info=True,
            )
            raise
        except Exception as e_unexp:  # Wrap unexpected errors
            self.logger.error(
                f"Unexpected error removing Windows service '{self.windows_service_name}': {e_unexp}",
                exc_info=True,
            )
            raise SystemError(
                f"Unexpected error during Windows service removal: {e_unexp}"
            ) from e_unexp

    def is_windows_service_active(self) -> bool:
        """Checks if the Windows Service for this server is currently running (Windows-only).

        Uses the ``sc.exe query <service_name>`` command and checks if the
        service ``STATE`` is ``RUNNING``.

        .. warning:: May require Administrator privileges for accurate results if
                     the service runs as a different user or if UAC interferes.

        Returns:
            bool: ``True`` if the service is detected in the 'RUNNING' state,
            ``False`` otherwise (e.g., stopped, service not found, error querying).

        Raises:
            SystemError: If called on a non-Windows system.
        """
        self._ensure_windows_for_service("is_windows_service_active")
        try:
            result = subprocess.check_output(
                ["sc", "query", self.windows_service_name],
                text=True,  # Decodes output as text
                stderr=subprocess.DEVNULL,  # Suppress stderr for non-existent service
                creationflags=subprocess.CREATE_NO_WINDOW,  # No console window
                encoding="utf-8",
                errors="replace",  # Specify encoding
            )
            # A running service will have a line like "        STATE              : 4  RUNNING"
            # Be careful with whitespace and case if system locale changes output format.
            # Using 'in' for substring search is safer.
            return "STATE" in result.upper() and "RUNNING" in result.upper()
        except subprocess.CalledProcessError:
            # This error typically occurs if the service does not exist or other sc query issues.
            self.logger.debug(
                f"Windows service '{self.windows_service_name}' not found or error querying state."
            )
            return False
        except FileNotFoundError:  # sc.exe not found
            self.logger.error(
                "`sc.exe` command not found. Cannot check Windows service active status."
            )
            return False
        except Exception as e_check:  # Catch any other unexpected error
            self.logger.error(
                f"Unexpected error checking Windows service active status for '{self.windows_service_name}': {e_check}",
                exc_info=True,
            )
            return False

    def is_windows_service_enabled(self) -> bool:
        """Checks if the Windows Service is enabled (start type is Automatic) (Windows-only).

        Uses the ``sc.exe qc <service_name>`` command (query configuration) and
        checks if the ``START_TYPE`` is ``AUTO_START``.

        .. warning:: May require Administrator privileges for accurate results.

        Returns:
            bool: ``True`` if the service start type is 'AUTO_START', ``False``
            otherwise (e.g., 'DEMAND_START', 'DISABLED', service not found, error querying).

        Raises:
            SystemError: If called on a non-Windows system.
        """
        self._ensure_windows_for_service("is_windows_service_enabled")
        try:
            result = subprocess.check_output(
                ["sc", "qc", self.windows_service_name],
                text=True,  # Decodes output as text
                stderr=subprocess.DEVNULL,  # Suppress stderr
                creationflags=subprocess.CREATE_NO_WINDOW,  # No console window
                encoding="utf-8",
                errors="replace",  # Specify encoding
            )
            # An enabled service (auto start) will have a line like "        START_TYPE         : 2   AUTO_START"
            # Some systems might just say "AUTO START" (without underscore).
            return (
                "START_TYPE" in result.upper()
                and "AUTO_START" in result.upper().replace("_", "")
            )
        except subprocess.CalledProcessError:
            self.logger.debug(
                f"Windows service '{self.windows_service_name}' not found or error querying config for enabled status."
            )
            return False
        except FileNotFoundError:  # sc.exe not found
            self.logger.error(
                "`sc.exe` command not found. Cannot check Windows service enabled status."
            )
            return False
        except Exception as e_check:  # Catch any other unexpected error
            self.logger.error(
                f"Unexpected error checking Windows service enabled status for '{self.windows_service_name}': {e_check}",
                exc_info=True,
            )
            return False
