"""
Standalone functions for managing the Web UI system service.

This module provides functions to interface with the operating system's service
manager (systemd, Windows Services) to control the Bedrock Server Manager Web UI service.
"""

import logging
import os
import platform
import shutil
import subprocess
from typing import Optional

from ..config.const import (
    EXPATH,
    WEB_SERVICE_SYSTEMD_NAME,
    WEB_SERVICE_WINDOWS_DISPLAY_NAME,
    WEB_SERVICE_WINDOWS_NAME_INTERNAL,
    app_name_title,
)
from ..error import (
    AppFileNotFoundError,
    CommandNotFoundError,
    FileOperationError,
    MissingArgumentError,
    PermissionsError,
    SystemError,
)

if platform.system() == "Linux":
    from .system import linux as system_linux_utils
elif platform.system() == "Windows":
    from .system import windows as system_windows_utils

logger = logging.getLogger(__name__)


def _ensure_linux_for_web_service(operation_name: str) -> None:
    """Ensures the current OS is Linux before proceeding with a Web UI systemd operation."""
    if platform.system() != "Linux":
        msg = f"Web UI Systemd operation '{operation_name}' is only supported on Linux. Current OS: {platform.system()}"
        logger.warning(msg)
        raise SystemError(msg)


def _ensure_windows_for_web_service(operation_name: str) -> None:
    """Ensures the current OS is Windows before proceeding with a Web UI service operation."""
    if platform.system() != "Windows":
        msg = f"Web UI Windows Service operation '{operation_name}' is only supported on Windows. Current OS: {platform.system()}"
        logger.warning(msg)
        raise SystemError(msg)


def _build_web_service_start_command() -> str:
    """Builds the command string used to start the Web UI as a service."""
    if not EXPATH or not os.path.isfile(EXPATH):
        raise AppFileNotFoundError(str(EXPATH), "Manager executable for Web UI service")

    exe_path_to_use = EXPATH
    if (
        " " in exe_path_to_use
        and not exe_path_to_use.startswith('"')
        and not exe_path_to_use.endswith('"')
    ):
        exe_path_to_use = f'"{exe_path_to_use}"'

    return f"{exe_path_to_use} web start --mode direct"


def create_web_service_file(  # noqa: C901
    app_data_dir: str,
    system: bool = False,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> None:
    """Creates or updates the system service file/entry for the Web UI."""
    os_type = platform.system()
    start_command = _build_web_service_start_command()

    if os_type == "Linux":
        _ensure_linux_for_web_service("create_web_service_file")
        assert EXPATH is not None
        stop_command_exe_path = EXPATH
        if (
            " " in stop_command_exe_path
            and not stop_command_exe_path.startswith('"')
            and not stop_command_exe_path.endswith('"')
        ):
            stop_command_exe_path = f'"{stop_command_exe_path}"'
        stop_command = f"{stop_command_exe_path} web stop"

        description = f"{app_name_title} Web UI Service"
        working_dir = app_data_dir
        if not os.path.isdir(working_dir):
            try:
                os.makedirs(working_dir, exist_ok=True)
                logger.debug(f"Ensured working directory exists: {working_dir}")
            except OSError as e:
                raise FileOperationError(
                    f"Failed to create working directory {working_dir} for service: {e}"
                )

        logger.info(
            f"Creating/updating systemd service file '{WEB_SERVICE_SYSTEMD_NAME}' for Web UI."
        )
        try:
            system_linux_utils.create_systemd_service_file(
                service_name_full=WEB_SERVICE_SYSTEMD_NAME,
                description=description,
                system=system,
                working_directory=working_dir,
                exec_start_command=start_command,
                exec_stop_command=stop_command,
                service_type="simple",
                restart_policy="on-failure",
                restart_sec=10,
                after_targets="network.target",
            )
            logger.info(
                f"Systemd service file for '{WEB_SERVICE_SYSTEMD_NAME}' created/updated successfully."
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
        _ensure_windows_for_web_service("create_web_service_file")
        description = f"Manages the {app_name_title} Web UI."

        if not EXPATH or not os.path.isfile(EXPATH):
            raise AppFileNotFoundError(
                str(EXPATH), "Manager executable (EXEPATH) for Web UI service"
            )

        quoted_main_exepath = f"{EXPATH}"
        actual_svc_name_arg = f'"{WEB_SERVICE_WINDOWS_NAME_INTERNAL}"'
        windows_service_binpath_command = (
            f"{quoted_main_exepath} service _run-web {actual_svc_name_arg}"
        )

        logger.info(
            f"Creating/updating Windows service '{WEB_SERVICE_WINDOWS_NAME_INTERNAL}' for Web UI."
        )
        logger.debug(
            f"Service binPath command will be: {windows_service_binpath_command}"
        )

        try:
            system_windows_utils.create_windows_service(
                service_name=WEB_SERVICE_WINDOWS_NAME_INTERNAL,
                display_name=WEB_SERVICE_WINDOWS_DISPLAY_NAME,
                description=description,
                command=windows_service_binpath_command,
                username=username,
                password=password,
            )
            logger.info(
                f"Windows service '{WEB_SERVICE_WINDOWS_NAME_INTERNAL}' created/updated successfully."
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
        raise SystemError(f"Web UI service creation is not supported on OS: {os_type}")


def check_web_service_exists(system: bool = False) -> bool:
    """Checks if the system service for the Web UI has been created."""
    os_type = platform.system()
    if os_type == "Linux":
        _ensure_linux_for_web_service("check_web_service_exists")
        return system_linux_utils.check_service_exists(
            WEB_SERVICE_SYSTEMD_NAME, system=system
        )
    elif os_type == "Windows":
        _ensure_windows_for_web_service("check_web_service_exists")
        return system_windows_utils.check_service_exists(
            WEB_SERVICE_WINDOWS_NAME_INTERNAL
        )
    else:
        logger.debug(f"Web service existence check not supported on OS: {os_type}")
        return False


def enable_web_service(system: bool = False) -> None:
    """Enables the Web UI system service to start automatically."""
    os_type = platform.system()
    if os_type == "Linux":
        _ensure_linux_for_web_service("enable_web_service")
        logger.info(
            f"Enabling systemd service '{WEB_SERVICE_SYSTEMD_NAME}' for Web UI."
        )
        system_linux_utils.enable_systemd_service(
            WEB_SERVICE_SYSTEMD_NAME, system=system
        )
        logger.info(f"Systemd service '{WEB_SERVICE_SYSTEMD_NAME}' enabled.")
    elif os_type == "Windows":
        _ensure_windows_for_web_service("enable_web_service")
        logger.info(
            f"Enabling Windows service '{WEB_SERVICE_WINDOWS_NAME_INTERNAL}' for Web UI."
        )
        system_windows_utils.enable_windows_service(WEB_SERVICE_WINDOWS_NAME_INTERNAL)
        logger.info(f"Windows service '{WEB_SERVICE_WINDOWS_NAME_INTERNAL}' enabled.")
    else:
        raise SystemError(f"Web UI service enabling is not supported on OS: {os_type}")


def disable_web_service(system: bool = False) -> None:
    """Disables the Web UI system service from starting automatically."""
    os_type = platform.system()
    if os_type == "Linux":
        _ensure_linux_for_web_service("disable_web_service")
        logger.info(
            f"Disabling systemd service '{WEB_SERVICE_SYSTEMD_NAME}' for Web UI."
        )
        system_linux_utils.disable_systemd_service(
            WEB_SERVICE_SYSTEMD_NAME, system=system
        )
        logger.info(f"Systemd service '{WEB_SERVICE_SYSTEMD_NAME}' disabled.")
    elif os_type == "Windows":
        _ensure_windows_for_web_service("disable_web_service")
        logger.info(
            f"Disabling Windows service '{WEB_SERVICE_WINDOWS_NAME_INTERNAL}' for Web UI."
        )
        system_windows_utils.disable_windows_service(WEB_SERVICE_WINDOWS_NAME_INTERNAL)
        logger.info(f"Windows service '{WEB_SERVICE_WINDOWS_NAME_INTERNAL}' disabled.")
    else:
        raise SystemError(f"Web UI service disabling is not supported on OS: {os_type}")


def remove_web_service_file(system: bool = False) -> bool:
    """Removes the Web UI system service definition."""
    os_type = platform.system()
    if os_type == "Linux":
        _ensure_linux_for_web_service("remove_web_service_file")
        service_file_path = system_linux_utils.get_systemd_service_file_path(
            WEB_SERVICE_SYSTEMD_NAME, system=system
        )
        if os.path.isfile(service_file_path):
            logger.info(f"Removing systemd service file: {service_file_path}")
            try:
                os.remove(service_file_path)
                systemctl_cmd = shutil.which("systemctl")
                if systemctl_cmd:
                    subprocess.run(
                        [systemctl_cmd, "--user", "daemon-reload"],
                        check=False,
                        capture_output=True,
                    )
                logger.info(
                    f"Removed systemd service file for Web UI '{WEB_SERVICE_SYSTEMD_NAME}' and reloaded daemon."
                )
                return True
            except OSError as e:
                raise FileOperationError(
                    f"Failed to remove systemd service file for Web UI: {e}"
                ) from e
        else:
            logger.debug(
                f"Systemd service file for Web UI '{WEB_SERVICE_SYSTEMD_NAME}' not found. No removal needed."
            )
            return True
    elif os_type == "Windows":
        _ensure_windows_for_web_service("remove_web_service_file")
        logger.info(
            f"Removing Windows service '{WEB_SERVICE_WINDOWS_NAME_INTERNAL}' for Web UI."
        )
        system_windows_utils.delete_windows_service(WEB_SERVICE_WINDOWS_NAME_INTERNAL)
        logger.info(
            f"Windows service '{WEB_SERVICE_WINDOWS_NAME_INTERNAL}' removed (if it existed)."
        )
        return True
    else:
        raise SystemError(f"Web UI service removal is not supported on OS: {os_type}")


def is_web_service_active(system: bool = False) -> bool:  # noqa: C901
    """Checks if the Web UI system service is currently active (running)."""
    os_type = platform.system()
    if os_type == "Linux":
        _ensure_linux_for_web_service("is_web_service_active")
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
                    WEB_SERVICE_SYSTEMD_NAME,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            is_active = process.returncode == 0 and process.stdout.strip() == "active"
            logger.debug(
                f"Web UI service '{WEB_SERVICE_SYSTEMD_NAME}' active status: {process.stdout.strip()} -> {is_active}"
            )
            return is_active
        except Exception as e:
            logger.error(
                f"Error checking Web UI systemd active status: {e}", exc_info=True
            )
            return False
    elif os_type == "Windows":
        _ensure_windows_for_web_service("is_web_service_active")
        sc_cmd = shutil.which("sc.exe")
        if not sc_cmd:
            logger.warning(
                "sc.exe command not found, cannot check Web UI service active state."
            )
            return False
        try:
            result = subprocess.check_output(
                [sc_cmd, "query", WEB_SERVICE_WINDOWS_NAME_INTERNAL],
                text=True,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            is_running = "STATE" in result and "RUNNING" in result
            logger.debug(
                f"Web UI service '{WEB_SERVICE_WINDOWS_NAME_INTERNAL}' running state from query: {is_running}"
            )
            return is_running
        except subprocess.CalledProcessError:
            logger.debug(
                f"Web UI service '{WEB_SERVICE_WINDOWS_NAME_INTERNAL}' not found or error during query."
            )
            return False
        except FileNotFoundError:
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


def is_web_service_enabled(system: bool = False) -> bool:  # noqa: C901
    """Checks if the Web UI system service is enabled for automatic startup."""
    os_type = platform.system()
    if os_type == "Linux":
        _ensure_linux_for_web_service("is_web_service_enabled")
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
                    WEB_SERVICE_SYSTEMD_NAME,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            is_enabled = process.returncode == 0 and process.stdout.strip() == "enabled"
            logger.debug(
                f"Web UI service '{WEB_SERVICE_SYSTEMD_NAME}' enabled status: {process.stdout.strip()} -> {is_enabled}"
            )
            return is_enabled
        except Exception as e:
            logger.error(
                f"Error checking Web UI systemd enabled status: {e}", exc_info=True
            )
            return False
    elif os_type == "Windows":
        _ensure_windows_for_web_service("is_web_service_enabled")
        sc_cmd = shutil.which("sc.exe")
        if not sc_cmd:
            logger.warning(
                "sc.exe command not found, cannot check Web UI service enabled state."
            )
            return False
        try:
            result = subprocess.check_output(
                [sc_cmd, "qc", WEB_SERVICE_WINDOWS_NAME_INTERNAL],
                text=True,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            is_auto_start = "START_TYPE" in result and "AUTO_START" in result
            logger.debug(
                f"Web UI service '{WEB_SERVICE_WINDOWS_NAME_INTERNAL}' auto_start state from qc: {is_auto_start}"
            )
            return is_auto_start
        except subprocess.CalledProcessError:
            logger.debug(
                f"Web UI service '{WEB_SERVICE_WINDOWS_NAME_INTERNAL}' not found or error during qc."
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
