import logging
import os
import platform
import shutil
import subprocess
from typing import Optional

from bedrock_server_manager.error import (
    AppFileNotFoundError,
    CommandNotFoundError,
    FileOperationError,
    MissingArgumentError,
    PermissionsError,
    SystemError,
)

if platform.system() == "Linux":
    from bedrock_server_manager.core.system import linux as system_linux_utils
elif platform.system() == "Windows":
    from bedrock_server_manager.core.system import windows as system_windows_utils


logger = logging.getLogger(__name__)


class WebServiceMixin:
    """
    Mixin class for BedrockServerManager that handles Web UI system service management.
    """

    def _ensure_linux_for_web_service(self, operation_name: str) -> None:
        """Ensures the current OS is Linux before proceeding with a Web UI systemd operation.

        Args:
            operation_name (str): The name of the operation being attempted,
                used in the error message if the OS is not Linux.

        Raises:
            SystemError: If the current operating system is not Linux.
        """
        if self.get_os_type() != "Linux":
            msg = f"Web UI Systemd operation '{operation_name}' is only supported on Linux. Current OS: {self.get_os_type()}"
            logger.warning(msg)
            raise SystemError(msg)

    def _ensure_windows_for_web_service(self, operation_name: str) -> None:
        """Ensures the current OS is Windows before proceeding with a Web UI service operation.

        Args:
            operation_name (str): The name of the operation being attempted,
                used in the error message if the OS is not Windows.

        Raises:
            SystemError: If the current operating system is not Windows.
        """
        if self.get_os_type() != "Windows":
            msg = f"Web UI Windows Service operation '{operation_name}' is only supported on Windows. Current OS: {self.get_os_type()}"
            logger.warning(msg)
            raise SystemError(msg)

    def _build_web_service_start_command(self) -> str:
        """Builds the command string used to start the Web UI as a service.

        This command typically involves the application executable (:attr:`._expath`)
        followed by arguments to start the web server in "direct" mode.
        The executable path is quoted if it contains spaces.

        Returns:
            str: The fully constructed command string.

        Raises:
            AppFileNotFoundError: If the manager executable path (:attr:`._expath`)
                is not configured or the file does not exist.
        """
        if not self._expath or not os.path.isfile(self._expath):
            raise AppFileNotFoundError(
                str(self._expath), "Manager executable for Web UI service"
            )

        exe_path_to_use = self._expath
        # Quote executable path if it contains spaces and isn't already quoted.
        # This is particularly important for Windows `binPath`.
        if " " in exe_path_to_use and not (
            exe_path_to_use.startswith('"') and exe_path_to_use.endswith('"')
        ):
            exe_path_to_use = f'"{exe_path_to_use}"'

        command_parts = [exe_path_to_use, "web", "start", "--mode", "direct"]

        return " ".join(command_parts)

    def create_web_service_file(
        self,
        system: bool = False,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        """Creates or updates the system service file/entry for the Web UI.

        This method handles the OS-specific logic for creating a system service
        that will run the Bedrock Server Manager Web UI.

            - On Linux, it creates a systemd user service file using
              :func:`~.core.system.linux.create_systemd_service_file`.
              The service will be named based on :attr:`._WEB_SERVICE_SYSTEMD_NAME`.
            - On Windows, it creates a new Windows Service using
              :func:`~.core.system.windows.create_windows_service`.
              The service will be named based on :attr:`._WEB_SERVICE_WINDOWS_NAME_INTERNAL`
              and :attr:`._WEB_SERVICE_WINDOWS_DISPLAY_NAME`.

        The start command for the service is constructed by :meth:`._build_web_service_start_command`.
        The application data directory (:attr:`._app_data_dir`) is typically used as the
        working directory for the service.

        Raises:
            SystemError: If the current operating system is not supported (not Linux or Windows),
                or if underlying system utility commands fail during service creation.
            AppFileNotFoundError: If the main manager executable path (:attr:`._expath`)
                is not found or configured.
            FileOperationError: If file or directory operations fail (e.g., creating
                the working directory for the service, or writing the systemd file).
            PermissionsError: On Windows, if the operation is not performed with
                Administrator privileges. On Linux, if user service directories
                are not writable.
            CommandNotFoundError: If essential system commands like ``systemctl`` (Linux)
                or ``sc.exe`` (Windows) are not found in the system's PATH.
            MissingArgumentError: If required internal values for service creation are missing.
        """

        os_type = self.get_os_type()
        start_command = self._build_web_service_start_command()

        if os_type == "Linux":
            self._ensure_linux_for_web_service("create_web_service_file")

            stop_command_exe_path = self._expath
            if " " in stop_command_exe_path and not (
                stop_command_exe_path.startswith('"')
                and stop_command_exe_path.endswith('"')
            ):
                stop_command_exe_path = f'"{stop_command_exe_path}"'
            stop_command = f"{stop_command_exe_path} web stop"  # Generic web stop

            description = f"{self._app_name_title} Web UI Service"
            # Use app_data_dir as working directory; ensure it exists.
            working_dir = self._app_data_dir
            if not os.path.isdir(working_dir):
                try:
                    os.makedirs(working_dir, exist_ok=True)
                    logger.debug(f"Ensured working directory exists: {working_dir}")
                except OSError as e:
                    raise FileOperationError(
                        f"Failed to create working directory {working_dir} for service: {e}"
                    )

            logger.info(
                f"Creating/updating systemd service file '{self._WEB_SERVICE_SYSTEMD_NAME}' for Web UI."
            )
            try:
                system_linux_utils.create_systemd_service_file(
                    service_name_full=self._WEB_SERVICE_SYSTEMD_NAME,
                    description=description,
                    system=system,
                    working_directory=working_dir,
                    exec_start_command=start_command,
                    exec_stop_command=stop_command,
                    service_type="simple",  # Web UI is a simple foreground process when in 'direct' mode
                    restart_policy="on-failure",
                    restart_sec=10,
                    after_targets="network.target",  # Ensures network is up
                )
                logger.info(
                    f"Systemd service file for '{self._WEB_SERVICE_SYSTEMD_NAME}' created/updated successfully."
                )
            except (
                MissingArgumentError,
                SystemError,
                CommandNotFoundError,
                AppFileNotFoundError,
                FileOperationError,
            ) as e:
                logger.error(
                    f"Failed to create/update systemd service file for Web UI: {e}"
                )
                raise

        elif os_type == "Windows":
            self._ensure_windows_for_web_service("create_web_service_file")
            description = f"Manages the {self._app_name_title} Web UI."

            if not self._expath or not os.path.isfile(self._expath):
                raise AppFileNotFoundError(
                    str(self._expath), "Manager executable (EXEPATH) for Web UI service"
                )

            # Quote paths and arguments appropriately for the command line.
            quoted_main_exepath = (
                f"{self._expath}"  # The main application executable that has the CLI.
            )

            # Arguments for the `_run-svc` command:
            # 1. The actual service name (this service will register itself with SCM using this name).
            actual_svc_name_arg = f'"{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}"'

            # Construct the full command for binPath
            windows_service_binpath_command_parts = [
                quoted_main_exepath,
                "service",  # Main command group
                "_run-web",  # The internal service runner command
                actual_svc_name_arg,
            ]

            windows_service_binpath_command = " ".join(
                windows_service_binpath_command_parts
            )

            logger.info(
                f"Creating/updating Windows service '{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}' for Web UI."
            )
            logger.debug(
                f"Service binPath command will be: {windows_service_binpath_command}"
            )

            try:
                system_windows_utils.create_windows_service(
                    service_name=self._WEB_SERVICE_WINDOWS_NAME_INTERNAL,
                    display_name=self._WEB_SERVICE_WINDOWS_DISPLAY_NAME,
                    description=description,
                    command=windows_service_binpath_command,
                    username=username,
                    password=password,
                )
                logger.info(
                    f"Windows service '{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}' created/updated successfully."
                )
            except (
                MissingArgumentError,
                SystemError,
                PermissionsError,
                CommandNotFoundError,
                AppFileNotFoundError,
                FileOperationError,
            ) as e:
                logger.error(f"Failed to create/update Windows service for Web UI: {e}")
                raise
        else:
            raise SystemError(
                f"Web UI service creation is not supported on OS: {os_type}"
            )

    def check_web_service_exists(self, system: bool = False) -> bool:
        """Checks if the system service for the Web UI has been created.

        Delegates to OS-specific checks:
        - On Linux, uses :func:`~.core.system.linux.check_service_exists` with :attr:`._WEB_SERVICE_SYSTEMD_NAME`.
        - On Windows, uses :func:`~.core.system.windows.check_service_exists` with :attr:`._WEB_SERVICE_WINDOWS_NAME_INTERNAL`.

        Returns:
            bool: ``True`` if the Web UI service definition exists on the system,
            ``False`` otherwise or if the OS is not supported.
        """
        os_type = self.get_os_type()
        if os_type == "Linux":
            self._ensure_linux_for_web_service("check_web_service_exists")
            return system_linux_utils.check_service_exists(
                self._WEB_SERVICE_SYSTEMD_NAME, system=system
            )
        elif os_type == "Windows":
            self._ensure_windows_for_web_service("check_web_service_exists")
            return system_windows_utils.check_service_exists(
                self._WEB_SERVICE_WINDOWS_NAME_INTERNAL
            )
        else:
            logger.debug(f"Web service existence check not supported on OS: {os_type}")
            return False

    def enable_web_service(self, system: bool = False) -> None:
        """Enables the Web UI system service to start automatically.

        On Linux, this typically means enabling the systemd service to start on boot or user login.
        Uses :func:`~.core.system.linux.enable_systemd_service`.
        On Windows, this sets the service's start type to "Automatic".
        Uses :func:`~.core.system.windows.enable_windows_service`.

        Raises:
            SystemError: If the OS is not supported or if the underlying
                system command (e.g., ``systemctl``, ``sc.exe``) fails.
            CommandNotFoundError: If system utilities are not found.
            PermissionsError: On Windows, if not run with Administrator privileges.
        """
        os_type = self.get_os_type()
        if os_type == "Linux":
            self._ensure_linux_for_web_service("enable_web_service")
            logger.info(
                f"Enabling systemd service '{self._WEB_SERVICE_SYSTEMD_NAME}' for Web UI."
            )
            system_linux_utils.enable_systemd_service(
                self._WEB_SERVICE_SYSTEMD_NAME, system=system
            )
            logger.info(f"Systemd service '{self._WEB_SERVICE_SYSTEMD_NAME}' enabled.")
        elif os_type == "Windows":
            self._ensure_windows_for_web_service("enable_web_service")
            logger.info(
                f"Enabling Windows service '{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}' for Web UI."
            )
            system_windows_utils.enable_windows_service(
                self._WEB_SERVICE_WINDOWS_NAME_INTERNAL
            )
            logger.info(
                f"Windows service '{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}' enabled."
            )
        else:
            raise SystemError(
                f"Web UI service enabling is not supported on OS: {os_type}"
            )

    def disable_web_service(self, system: bool = False) -> None:
        """Disables the Web UI system service from starting automatically.

        On Linux, this typically means disabling the systemd service.
        Uses :func:`~.core.system.linux.disable_systemd_service`.
        On Windows, this sets the service's start type to "Manual" or "Disabled".
        Uses :func:`~.core.system.windows.disable_windows_service`.

        Raises:
            SystemError: If the OS is not supported or if the underlying
                system command fails.
            CommandNotFoundError: If system utilities are not found.
            PermissionsError: On Windows, if not run with Administrator privileges.
        """
        os_type = self.get_os_type()
        if os_type == "Linux":
            self._ensure_linux_for_web_service("disable_web_service")
            logger.info(
                f"Disabling systemd service '{self._WEB_SERVICE_SYSTEMD_NAME}' for Web UI."
            )
            system_linux_utils.disable_systemd_service(
                self._WEB_SERVICE_SYSTEMD_NAME, system=system
            )
            logger.info(f"Systemd service '{self._WEB_SERVICE_SYSTEMD_NAME}' disabled.")
        elif os_type == "Windows":
            self._ensure_windows_for_web_service("disable_web_service")
            logger.info(
                f"Disabling Windows service '{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}' for Web UI."
            )
            system_windows_utils.disable_windows_service(
                self._WEB_SERVICE_WINDOWS_NAME_INTERNAL
            )
            logger.info(
                f"Windows service '{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}' disabled."
            )
        else:
            raise SystemError(
                f"Web UI service disabling is not supported on OS: {os_type}"
            )

    def remove_web_service_file(self, system: bool = False) -> bool:
        """Removes the Web UI system service definition.

        .. warning::
            This is a destructive operation. The service should ideally be stopped
            and disabled before removal. After removal, it must be recreated using
            :meth:`.create_web_service_file` if needed again.

        On Linux, this removes the systemd user service file and reloads the systemd daemon.

        Uses :func:`os.remove` and ``systemctl --user daemon-reload``.

        On Windows, this deletes the service using :func:`~.core.system.windows.delete_windows_service`.

        Returns:
            bool
                ``True`` if the service was successfully removed or if it was
                already not found (considered idempotent for removal).

        Raises:
            SystemError
                If the OS is not supported.
            FileOperationError
                On Linux, if removing the service file fails.
            CommandNotFoundError
                If system utilities are not found.
            PermissionsError
                On Windows, if not run with Administrator privileges.

                Details of what "Various" includes, for example, it can include
                    :class:`~.error.SubprocessError` if ``sc.exe delete`` fails.
        """
        os_type = self.get_os_type()
        if os_type == "Linux":
            self._ensure_linux_for_web_service("remove_web_service_file")
            service_file_path = system_linux_utils.get_systemd_service_file_path(
                self._WEB_SERVICE_SYSTEMD_NAME, system=system
            )
            if os.path.isfile(service_file_path):
                logger.info(f"Removing systemd service file: {service_file_path}")
                try:
                    os.remove(service_file_path)
                    systemctl_cmd = shutil.which("systemctl")
                    if systemctl_cmd:  # Reload daemon if systemctl is available
                        subprocess.run(
                            [systemctl_cmd, "--user", "daemon-reload"],
                            check=False,
                            capture_output=True,
                        )
                    logger.info(
                        f"Removed systemd service file for Web UI '{self._WEB_SERVICE_SYSTEMD_NAME}' and reloaded daemon."
                    )
                    return True
                except OSError as e:
                    raise FileOperationError(
                        f"Failed to remove systemd service file for Web UI: {e}"
                    ) from e
            else:
                logger.debug(
                    f"Systemd service file for Web UI '{self._WEB_SERVICE_SYSTEMD_NAME}' not found. No removal needed."
                )
                return (
                    True  # Consistent with original mixin: true if not found or removed
                )
        elif os_type == "Windows":
            self._ensure_windows_for_web_service("remove_web_service_file")
            logger.info(
                f"Removing Windows service '{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}' for Web UI."
            )
            system_windows_utils.delete_windows_service(
                self._WEB_SERVICE_WINDOWS_NAME_INTERNAL
            )  # This should handle if not exists gracefully or raise
            logger.info(
                f"Windows service '{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}' removed (if it existed)."
            )
            return True  # Assuming delete_windows_service is idempotent or handles "not found"
        else:
            raise SystemError(
                f"Web UI service removal is not supported on OS: {os_type}"
            )

    def is_web_service_active(self, system: bool = False) -> bool:
        """Checks if the Web UI system service is currently active (running).

        Delegates to OS-specific checks:

            - On Linux, uses ``systemctl --user is-active`` for the service named
              by :attr:`._WEB_SERVICE_SYSTEMD_NAME`.
            - On Windows, uses ``sc query`` for the service named by
              :attr:`._WEB_SERVICE_WINDOWS_NAME_INTERNAL`.

        Returns ``False`` if the OS is not supported, if system utilities
        (``systemctl``, ``sc.exe``) are not found, or if the service is not active.
        Errors during the check are logged.

        Returns:
            bool: ``True`` if the Web UI service is determined to be active,
            ``False`` otherwise.
        """
        os_type = self.get_os_type()
        if os_type == "Linux":
            self._ensure_linux_for_web_service("is_web_service_active")
            systemctl_cmd = shutil.which("systemctl")
            if not systemctl_cmd:
                logger.warning(
                    "systemctl command not found, cannot check Web UI service active state."
                )
                return False
            try:
                process = subprocess.run(
                    [
                        systemctl_cmd,
                        "--user" if not system else "",
                        "is-active",
                        self._WEB_SERVICE_SYSTEMD_NAME,
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                is_active = (
                    process.returncode == 0 and process.stdout.strip() == "active"
                )
                logger.debug(
                    f"Web UI service '{self._WEB_SERVICE_SYSTEMD_NAME}' active status: {process.stdout.strip()} -> {is_active}"
                )
                return is_active
            except Exception as e:
                logger.error(
                    f"Error checking Web UI systemd active status: {e}", exc_info=True
                )
                return False
        elif os_type == "Windows":
            self._ensure_windows_for_web_service("is_web_service_active")
            sc_cmd = shutil.which("sc.exe")
            if not sc_cmd:
                logger.warning(
                    "sc.exe command not found, cannot check Web UI service active state."
                )
                return False
            try:
                # Use 'sc query' to check the state of the service.
                result = subprocess.check_output(
                    [sc_cmd, "query", self._WEB_SERVICE_WINDOWS_NAME_INTERNAL],
                    text=True,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(
                        subprocess, "CREATE_NO_WINDOW", 0
                    ),  # CREATE_NO_WINDOW for Windows
                )
                is_running = "STATE" in result and "RUNNING" in result
                logger.debug(
                    f"Web UI service '{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}' running state from query: {is_running}"
                )
                return is_running
            except (
                subprocess.CalledProcessError
            ):  # Service does not exist or other sc error
                logger.debug(
                    f"Web UI service '{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}' not found or error during query."
                )
                return False
            except (
                FileNotFoundError
            ):  # sc.exe not found (should be caught by shutil.which)
                logger.warning("`sc.exe` command not found unexpectedly.")
                return False
            except Exception as e:
                logger.error(
                    f"Error checking Web UI Windows service active status: {e}",
                    exc_info=True,
                )
                return False
        else:
            logger.debug(f"Web UI service active check not supported on OS: {os_type}")
            return False

    def is_web_service_enabled(self, system: bool = False) -> bool:
        """Checks if the Web UI system service is enabled for automatic startup.

        Delegates to OS-specific checks:

            - On Linux, uses ``systemctl --user is-enabled`` for the service named
              by :attr:`._WEB_SERVICE_SYSTEMD_NAME`.
            - On Windows, uses ``sc qc`` (query config) for the service named by
              :attr:`._WEB_SERVICE_WINDOWS_NAME_INTERNAL` to check if its start type
              is "AUTO_START".

        Returns ``False`` if the OS is not supported, if system utilities
        (``systemctl``, ``sc.exe``) are not found, or if the service is not enabled.
        Errors during the check are logged.

        Returns:
            bool: ``True`` if the Web UI service is determined to be enabled for
            automatic startup, ``False`` otherwise.
        """
        os_type = self.get_os_type()
        if os_type == "Linux":
            self._ensure_linux_for_web_service("is_web_service_enabled")
            systemctl_cmd = shutil.which("systemctl")
            if not systemctl_cmd:
                logger.warning(
                    "systemctl command not found, cannot check Web UI service enabled state."
                )
                return False
            try:
                process = subprocess.run(
                    [
                        systemctl_cmd,
                        "--user" if not system else "",
                        "is-enabled",
                        self._WEB_SERVICE_SYSTEMD_NAME,
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                # is-enabled can return "enabled", "enabled-runtime", etc.
                # "enabled" means it's set to start. Other statuses might also be considered "on".
                # For simplicity, strict "enabled" check.
                is_enabled = (
                    process.returncode == 0 and process.stdout.strip() == "enabled"
                )
                logger.debug(
                    f"Web UI service '{self._WEB_SERVICE_SYSTEMD_NAME}' enabled status: {process.stdout.strip()} -> {is_enabled}"
                )
                return is_enabled
            except Exception as e:
                logger.error(
                    f"Error checking Web UI systemd enabled status: {e}", exc_info=True
                )
                return False
        elif os_type == "Windows":
            self._ensure_windows_for_web_service("is_web_service_enabled")
            sc_cmd = shutil.which("sc.exe")
            if not sc_cmd:
                logger.warning(
                    "sc.exe command not found, cannot check Web UI service enabled state."
                )
                return False
            try:
                # Use 'sc qc' (query config) to check the start type.
                result = subprocess.check_output(
                    [sc_cmd, "qc", self._WEB_SERVICE_WINDOWS_NAME_INTERNAL],
                    text=True,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                is_auto_start = (
                    "START_TYPE" in result and "AUTO_START" in result
                )  # 2  AUTO_START
                logger.debug(
                    f"Web UI service '{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}' auto_start state from qc: {is_auto_start}"
                )
                return is_auto_start
            except (
                subprocess.CalledProcessError
            ):  # Service does not exist or other sc error
                logger.debug(
                    f"Web UI service '{self._WEB_SERVICE_WINDOWS_NAME_INTERNAL}' not found or error during qc."
                )
                return False
            except FileNotFoundError:
                logger.warning("`sc.exe` command not found unexpectedly.")
                return False
            except Exception as e:
                logger.error(
                    f"Error checking Web UI Windows service enabled status: {e}",
                    exc_info=True,
                )
                return False
        else:
            logger.debug(f"Web UI service enabled check not supported on OS: {os_type}")
            return False
