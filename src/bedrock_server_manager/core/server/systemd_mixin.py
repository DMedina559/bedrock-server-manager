# bedrock_server_manager/core/server/systemd_mixin.py
"""Provides the :class:`.ServerSystemdMixin` for the :class:`~.core.bedrock_server.BedrockServer` class.

This mixin encapsulates Linux-specific systemd user service management for a
Bedrock server instance. It enables creating, enabling, disabling, removing,
and checking the status of systemd user services designed to manage the
Bedrock server process. This facilitates running the server in the background
and enabling autostart capabilities on user login.

The functionality largely delegates to helper utilities in the
:mod:`~.core.system.linux` module, which interact with the ``systemctl --user``
command. All methods in this mixin will first verify that the operating system
is Linux; if not, they typically raise a :class:`~.error.SystemError`.
"""
import os
import platform
import shutil
import subprocess
from typing import Any, Optional

# Local application imports.
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.core.system import linux as system_linux_utils
from bedrock_server_manager.error import (
    SystemError,
    FileOperationError,
    AppFileNotFoundError,
    BSMError,
)


class ServerSystemdMixin(BedrockServerBaseMixin):
    """Manages a systemd user service for a Bedrock server instance (Linux-only).

    This mixin extends :class:`.BedrockServerBaseMixin` and provides methods
    to interact with systemd at the user level (``systemctl --user``). It allows
    for the creation of a ``.service`` file tailored to run the Bedrock server,
    enabling it to start on user login, run in the background, and be managed
    by systemd commands.

    All methods herein first check if the current OS is Linux using
    :meth:`._ensure_linux_for_systemd`; if not, they raise a
    :class:`~.error.SystemError`. Operations like creating, enabling,
    disabling, and removing service files largely delegate to utilities in
    :mod:`~.core.system.linux`.

    Key functionalities include:

        - Generating the standard systemd service name for the server.
        - Checking if the service file exists.
        - Creating or updating the ``.service`` file content.
        - Enabling or disabling the service for autostart.
        - Removing the service file.
        - Checking if the service is currently active or enabled.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initializes the ServerSystemdMixin.

        Calls ``super().__init__(*args, **kwargs)`` to participate in cooperative
        multiple inheritance. It relies on attributes initialized by
        :class:`.BedrockServerBaseMixin` such as `server_name`, `server_dir`,
        `manager_expath` (path to the application script/executable used in service
        commands), and `os_type`.

        Args:
            *args (Any): Variable length argument list passed to `super()`.
            **kwargs (Any): Arbitrary keyword arguments passed to `super()`.
        """
        super().__init__(*args, **kwargs)
        # Attributes from BedrockServerBaseMixin are available.

    def _ensure_linux_for_systemd(self, operation_name: str) -> None:
        """Internal helper to verify the OS is Linux before a systemd operation.

        Args:
            operation_name (str): The name of the systemd-related operation
                being attempted (e.g., "create_systemd_service_file"). Used for logging.

        Raises:
            SystemError: If the current operating system (``self.os_type``) is not "Linux".
        """
        if self.os_type != "Linux":
            msg = f"Systemd operation '{operation_name}' is only supported on Linux. Current OS: {self.os_type}"
            self.logger.error(msg)  # Log as error as it's a misuse of the mixin
            raise SystemError(msg)

    @property
    def systemd_service_name_full(self) -> str:
        """str: The full systemd service unit name for this server instance.

        Constructed as ``bedrock-<server_name>.service`` (e.g., "bedrock-MyServer.service").
        This name is used when interacting with ``systemctl --user``.
        """
        return f"bedrock-{self.server_name}.service"

    def check_systemd_service_file_exists(self) -> bool:
        """Checks if the systemd user service file for this server exists (Linux-only).

        Delegates to :func:`~.core.system.linux.check_service_exists`.

        Returns:
            bool: ``True`` if the service file exists, ``False`` otherwise or if not on Linux.

        Raises:
            SystemError: If called on a non-Linux system (via :meth:`._ensure_linux_for_systemd`).
        """
        self._ensure_linux_for_systemd("check_systemd_service_file_exists")
        return system_linux_utils.check_service_exists(self.systemd_service_name_full)

    def create_systemd_service_file(self) -> None:
        """Creates or updates the systemd user service file for this server (Linux-only).

        This method constructs the necessary parameters (description, working directory,
        start/stop commands using :attr:`.BedrockServerBaseMixin.manager_expath`) and
        then delegates the actual file creation and ``systemctl --user daemon-reload``
        to :func:`~.core.system.linux.create_systemd_service_file`.

        The service is typically configured as ``Type=simple`` and ``Restart=on-failure``.

        Raises:
            SystemError: If called on a non-Linux system, or if ``systemctl``
                         operations fail (propagated from ``system_linux_utils``).
            AppFileNotFoundError: If :attr:`.BedrockServerBaseMixin.manager_expath`
                                  is not found, or if `server_dir` is invalid.
            FileOperationError: If creating directories or writing the service file fails.
            CommandNotFoundError: If ``systemctl`` is not found.
            MissingArgumentError: If required arguments for delegation are missing.
        """
        self._ensure_linux_for_systemd("create_systemd_service_file")

        if not self.manager_expath or not os.path.isfile(self.manager_expath):
            raise AppFileNotFoundError(
                str(
                    self.manager_expath
                ),  # Ensure manager_expath is str for AppFileNotFoundError
                f"Manager executable path for server '{self.server_name}' service file not found or invalid.",
            )

        description = f"Minecraft Bedrock Server: {self.server_name}"
        working_directory = self.server_dir  # From BaseServerMixin
        # Construct ExecStart to call this application's 'server start' command
        exec_start = f'"{self.manager_expath}" server start --server "{self.server_name}" --mode direct'
        # Construct ExecStop to call this application's 'server stop' command
        exec_stop = f'"{self.manager_expath}" server stop --server "{self.server_name}"'
        # exec_start_pre is not currently used for Bedrock server services.
        exec_start_pre: Optional[str] = None

        self.logger.info(
            f"Creating/updating systemd service file '{self.systemd_service_name_full}' for server '{self.server_name}'."
        )
        try:
            system_linux_utils.create_systemd_service_file(
                service_name_full=self.systemd_service_name_full,
                description=description,
                working_directory=working_directory,
                exec_start_command=exec_start,
                exec_stop_command=exec_stop,
                exec_start_pre_command=exec_start_pre,
                service_type="simple",  # Bedrock server runs as a simple foreground process
                restart_policy="on-failure",
                restart_sec=10,
                after_targets="network.target",  # Standard target to wait for network
            )
            self.logger.info(
                f"Systemd service file for '{self.systemd_service_name_full}' created/updated successfully."
            )
        except BSMError:  # Re-raise known BSM errors
            self.logger.error(
                f"Failed to create/update systemd service file for '{self.systemd_service_name_full}'.",
                exc_info=True,
            )
            raise
        except Exception as e_unexp:  # Wrap unexpected errors
            self.logger.error(
                f"Unexpected error creating/updating systemd service file for '{self.systemd_service_name_full}': {e_unexp}",
                exc_info=True,
            )
            raise SystemError(
                f"Unexpected error during systemd file creation: {e_unexp}"
            ) from e_unexp

    def enable_systemd_service(self) -> None:
        """Enables the systemd user service for this server to start on user login (Linux-only).

        Delegates to :func:`~.core.system.linux.enable_systemd_service`.

        Raises:
            SystemError: If not on Linux, if the service file doesn't exist,
                         or if the ``systemctl --user enable`` command fails.
            CommandNotFoundError: If ``systemctl`` is not found.
            MissingArgumentError: If the service name is invalid.
        """
        self._ensure_linux_for_systemd("enable_systemd_service")
        self.logger.info(
            f"Enabling systemd service '{self.systemd_service_name_full}' for server '{self.server_name}'."
        )
        try:
            system_linux_utils.enable_systemd_service(self.systemd_service_name_full)
            self.logger.info(
                f"Systemd service '{self.systemd_service_name_full}' enabled successfully."
            )
        except BSMError:  # Re-raise known BSM errors
            self.logger.error(
                f"Failed to enable systemd service '{self.systemd_service_name_full}'.",
                exc_info=True,
            )
            raise
        except Exception as e_unexp:  # Wrap unexpected errors
            self.logger.error(
                f"Unexpected error enabling systemd service '{self.systemd_service_name_full}': {e_unexp}",
                exc_info=True,
            )
            raise SystemError(
                f"Unexpected error during systemd service enable: {e_unexp}"
            ) from e_unexp

    def disable_systemd_service(self) -> None:
        """Disables the systemd user service for this server from starting on user login (Linux-only).

        Delegates to :func:`~.core.system.linux.disable_systemd_service`.

        Raises:
            SystemError: If not on Linux or if the ``systemctl --user disable`` command fails.
            CommandNotFoundError: If ``systemctl`` is not found.
            MissingArgumentError: If the service name is invalid.
        """
        self._ensure_linux_for_systemd("disable_systemd_service")
        self.logger.info(
            f"Disabling systemd service '{self.systemd_service_name_full}' for server '{self.server_name}'."
        )
        try:
            system_linux_utils.disable_systemd_service(self.systemd_service_name_full)
            self.logger.info(
                f"Systemd service '{self.systemd_service_name_full}' disabled successfully."
            )
        except BSMError:  # Re-raise known BSM errors
            self.logger.error(
                f"Failed to disable systemd service '{self.systemd_service_name_full}'.",
                exc_info=True,
            )
            raise
        except Exception as e_unexp:  # Wrap unexpected errors
            self.logger.error(
                f"Unexpected error disabling systemd service '{self.systemd_service_name_full}': {e_unexp}",
                exc_info=True,
            )
            raise SystemError(
                f"Unexpected error during systemd service disable: {e_unexp}"
            ) from e_unexp

    def remove_systemd_service_file(self) -> bool:
        """Removes the systemd user service file for this server if it exists (Linux-only).

        After removing the file, it attempts to reload the systemd user daemon
        using ``systemctl --user daemon-reload``.

        Returns:
            bool: ``True`` if the file was successfully removed or if it did not exist
            initially. ``False`` if an ``OSError`` occurred during removal (though
            this method aims to raise :class:`~.error.FileOperationError` instead).

        Raises:
            SystemError: If called on a non-Linux system.
            FileOperationError: If removing the service file fails due to an ``OSError``.
        """
        self._ensure_linux_for_systemd("remove_systemd_service_file")

        service_file_to_remove = system_linux_utils.get_systemd_user_service_file_path(
            self.systemd_service_name_full
        )

        if os.path.isfile(service_file_to_remove):
            self.logger.info(
                f"Removing systemd service file: {service_file_to_remove} for server '{self.server_name}'."
            )
            try:
                os.remove(service_file_to_remove)
                self.logger.info(
                    f"Successfully removed systemd service file '{service_file_to_remove}'."
                )

                # After removing a file, the systemd daemon should be reloaded.
                systemctl_cmd = shutil.which("systemctl")
                if systemctl_cmd:
                    self.logger.debug(
                        "Reloading systemd user daemon after service file removal."
                    )
                    subprocess.run(
                        [systemctl_cmd, "--user", "daemon-reload"],
                        check=False,  # Don't raise error if reload fails, but log it
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                    )
                    # It's also good practice to reset failed state if any
                    subprocess.run(
                        [systemctl_cmd, "--user", "reset-failed"],
                        check=False,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                    )
                else:
                    self.logger.warning(
                        "'systemctl' command not found. Cannot reload systemd daemon after service file removal."
                    )
                return True
            except OSError as e_os:
                raise FileOperationError(
                    f"Failed to remove systemd service file '{service_file_to_remove}' for server '{self.server_name}': {e_os}"
                ) from e_os
        else:
            self.logger.debug(
                f"Systemd service file for '{self.systemd_service_name_full}' (server '{self.server_name}') not found. No removal needed."
            )
            return True

    def is_systemd_service_active(self) -> bool:
        """Checks if the systemd user service for this server is currently active (Linux-only).

        Uses ``systemctl --user is-active <service_name>``.

        Returns:
            bool: ``True`` if the service is active, ``False`` otherwise (including
            if `systemctl` is not found or if the OS is not Linux).

        Raises:
            SystemError: If called on a non-Linux system.
        """
        self._ensure_linux_for_systemd("is_systemd_service_active")
        systemctl_cmd = shutil.which("systemctl")
        if not systemctl_cmd:
            self.logger.warning(
                "'systemctl' command not found. Cannot check service active status."
            )
            return False

        try:
            process = subprocess.run(
                [systemctl_cmd, "--user", "is-active", self.systemd_service_name_full],
                capture_output=True,
                text=True,
                check=False,  # `is-active` returns non-zero for inactive
                encoding="utf-8",
                errors="replace",
            )
            # stdout.strip() will be "active" or "inactive" or "activating" etc.
            is_active = process.stdout.strip() == "active"
            self.logger.debug(
                f"Systemd service '{self.systemd_service_name_full}' is-active output: '{process.stdout.strip()}' -> {is_active}"
            )
            return is_active
        except Exception as e_check:  # Catch any subprocess or other errors
            self.logger.error(
                f"Error checking systemd active status for '{self.systemd_service_name_full}': {e_check}",
                exc_info=True,
            )
            return False

    def is_systemd_service_enabled(self) -> bool:
        """Checks if the systemd user service for this server is enabled to start on login (Linux-only).

        Uses ``systemctl --user is-enabled <service_name>``.

        Returns:
            bool: ``True`` if the service is enabled, ``False`` otherwise (including
            if `systemctl` is not found or if the OS is not Linux).

        Raises:
            SystemError: If called on a non-Linux system.
        """
        self._ensure_linux_for_systemd("is_systemd_service_enabled")
        systemctl_cmd = shutil.which("systemctl")
        if not systemctl_cmd:
            self.logger.warning(
                "'systemctl' command not found. Cannot check service enabled status."
            )
            return False

        try:
            process = subprocess.run(
                [systemctl_cmd, "--user", "is-enabled", self.systemd_service_name_full],
                capture_output=True,
                text=True,
                check=False,  # `is-enabled` returns non-zero for disabled
                encoding="utf-8",
                errors="replace",
            )
            # stdout.strip() will be "enabled", "disabled", "static", "masked", etc.
            is_enabled = process.stdout.strip() == "enabled"
            self.logger.debug(
                f"Systemd service '{self.systemd_service_name_full}' is-enabled output: '{process.stdout.strip()}' -> {is_enabled}"
            )
            return is_enabled
        except Exception as e_check:  # Catch any subprocess or other errors
            self.logger.error(
                f"Error checking systemd enabled status for '{self.systemd_service_name_full}': {e_check}",
                exc_info=True,
            )
            return False
