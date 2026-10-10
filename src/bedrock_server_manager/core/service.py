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
import sys
from typing import Optional

from ..config.const import (
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
from ..logging import log_operation_error

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
    exe_path_to_use = sys.executable
    if (
        " " in exe_path_to_use
        and not exe_path_to_use.startswith('"')
        and not exe_path_to_use.endswith('"')
    ):
        exe_path_to_use = f'"{exe_path_to_use}"'

    return f"{exe_path_to_use} -m bedrock_server_manager web start --mode direct"


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
        stop_command_exe_path = sys.executable
        if (
            " " in stop_command_exe_path
            and not stop_command_exe_path.startswith('"')
            and not stop_command_exe_path.endswith('"')
        ):
            stop_command_exe_path = f'"{stop_command_exe_path}"'
        stop_command = f"{stop_command_exe_path} -m bedrock_server_manager web stop"

        description = f"{app_name_title} Web UI Service"
        working_dir = app_data_dir
        if not os.path.isdir(working_dir):
            try:
                os.makedirs(working_dir, exist_ok=True)
                logger.debug("Ensured working directory exists: %s", working_dir)
            except OSError as e:
                raise FileOperationError(
                    f"Failed to create working directory {working_dir} for service: {e}"
                )

        logger.debug(
            "Creating/updating systemd service file '%s' for Web UI.",
            WEB_SERVICE_SYSTEMD_NAME,
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
                "Systemd service file for '%s' created/updated successfully.",
                WEB_SERVICE_SYSTEMD_NAME,
            )
        except (
            MissingArgumentError,
            SystemError,
            CommandNotFoundError,
            AppFileNotFoundError,
            FileOperationError,
        ) as e:
            log_operation_error(
                logger,
                "Failed to create/update systemd service file for Web UI: %s",
                e,
                error=e,
            )
            raise

    elif os_type == "Windows":
        _ensure_windows_for_web_service("create_web_service_file")
        description = f"Manages the {app_name_title} Web UI."

        quoted_main_exepath = f"{sys.executable}"
        if (
            " " in quoted_main_exepath
            and not quoted_main_exepath.startswith('"')
            and not quoted_main_exepath.endswith('"')
        ):
            quoted_main_exepath = f'"{quoted_main_exepath}"'

        actual_svc_name_arg = f'"{WEB_SERVICE_WINDOWS_NAME_INTERNAL}"'
        windows_service_binpath_command = f"{quoted_main_exepath} -m bedrock_server_manager service _run-web {actual_svc_name_arg}"

        logger.debug(
            "Creating/updating Windows service '%s' for Web UI.",
            WEB_SERVICE_WINDOWS_NAME_INTERNAL,
        )
        logger.debug(
            "Service binPath command will be: %s", windows_service_binpath_command
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
                "Windows service '%s' created/updated successfully.",
                WEB_SERVICE_WINDOWS_NAME_INTERNAL,
            )
        except (
            MissingArgumentError,
            SystemError,
            PermissionsError,
            CommandNotFoundError,
            AppFileNotFoundError,
            FileOperationError,
        ) as e:
            log_operation_error(
                logger,
                "Failed to create/update Windows service for Web UI: %s",
                e,
                error=e,
            )
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
        logger.debug("Web service existence check not supported on OS: %s", os_type)
        return False


def enable_web_service(system: bool = False) -> None:
    """Enables the Web UI system service to start automatically."""
    os_type = platform.system()
    if os_type == "Linux":
        _ensure_linux_for_web_service("enable_web_service")
        logger.debug(
            "Enabling systemd service '%s' for Web UI.", WEB_SERVICE_SYSTEMD_NAME
        )
        system_linux_utils.enable_systemd_service(
            WEB_SERVICE_SYSTEMD_NAME, system=system
        )
        logger.info("Systemd service '%s' enabled.", WEB_SERVICE_SYSTEMD_NAME)
    elif os_type == "Windows":
        _ensure_windows_for_web_service("enable_web_service")
        logger.debug(
            "Enabling Windows service '%s' for Web UI.",
            WEB_SERVICE_WINDOWS_NAME_INTERNAL,
        )
        system_windows_utils.enable_windows_service(WEB_SERVICE_WINDOWS_NAME_INTERNAL)
        logger.info("Windows service '%s' enabled.", WEB_SERVICE_WINDOWS_NAME_INTERNAL)
    else:
        raise SystemError(f"Web UI service enabling is not supported on OS: {os_type}")


def disable_web_service(system: bool = False) -> None:
    """Disables the Web UI system service from starting automatically."""
    os_type = platform.system()
    if os_type == "Linux":
        _ensure_linux_for_web_service("disable_web_service")
        logger.debug(
            "Disabling systemd service '%s' for Web UI.", WEB_SERVICE_SYSTEMD_NAME
        )
        system_linux_utils.disable_systemd_service(
            WEB_SERVICE_SYSTEMD_NAME, system=system
        )
        logger.info("Systemd service '%s' disabled.", WEB_SERVICE_SYSTEMD_NAME)
    elif os_type == "Windows":
        _ensure_windows_for_web_service("disable_web_service")
        logger.debug(
            "Disabling Windows service '%s' for Web UI.",
            WEB_SERVICE_WINDOWS_NAME_INTERNAL,
        )
        system_windows_utils.disable_windows_service(WEB_SERVICE_WINDOWS_NAME_INTERNAL)
        logger.info("Windows service '%s' disabled.", WEB_SERVICE_WINDOWS_NAME_INTERNAL)
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
            logger.debug("Removing systemd service file: %s", service_file_path)
            try:
                os.remove(service_file_path)
                systemctl_cmd = shutil.which("systemctl")
                if systemctl_cmd:
                    command = [systemctl_cmd]
                    if not system:
                        command.append("--user")
                    command.append("daemon-reload")
                    subprocess.run(
                        command,
                        check=False,
                        capture_output=True,
                    )
                logger.info(
                    "Removed systemd service file for Web UI '%s' and reloaded daemon.",
                    WEB_SERVICE_SYSTEMD_NAME,
                )
                return True
            except OSError as e:
                raise FileOperationError(
                    f"Failed to remove systemd service file for Web UI: {e}"
                ) from e
        else:
            logger.debug(
                "Systemd service file for Web UI '%s' not found. No removal needed.",
                WEB_SERVICE_SYSTEMD_NAME,
            )
            return True
    elif os_type == "Windows":
        _ensure_windows_for_web_service("remove_web_service_file")
        logger.debug(
            "Removing Windows service '%s' for Web UI.",
            WEB_SERVICE_WINDOWS_NAME_INTERNAL,
        )
        system_windows_utils.delete_windows_service(WEB_SERVICE_WINDOWS_NAME_INTERNAL)
        logger.info(
            "Windows service '%s' removed (if it existed).",
            WEB_SERVICE_WINDOWS_NAME_INTERNAL,
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
            command = [systemctl_cmd]
            if not system:
                command.append("--user")
            command.extend(["is-active", WEB_SERVICE_SYSTEMD_NAME])
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
            is_active = process.returncode == 0 and process.stdout.strip() == "active"
            logger.debug(
                "Web UI service '%s' active status: %s -> %s",
                WEB_SERVICE_SYSTEMD_NAME,
                process.stdout.strip(),
                is_active,
            )
            return is_active
        except Exception as e:
            log_operation_error(
                logger, "Error checking Web UI systemd active status: %s", e, error=e
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
                "Web UI service '%s' running state from query: %s",
                WEB_SERVICE_WINDOWS_NAME_INTERNAL,
                is_running,
            )
            return is_running
        except subprocess.CalledProcessError:
            logger.debug(
                "Web UI service '%s' not found or error during query.",
                WEB_SERVICE_WINDOWS_NAME_INTERNAL,
            )
            return False
        except FileNotFoundError:
            logger.warning("`sc.exe` command not found unexpectedly.")
            return False
        except Exception as e:
            log_operation_error(
                logger,
                "Error checking Web UI Windows service active status: %s",
                e,
                error=e,
            )
            return False
    else:
        logger.debug("Web UI service active check not supported on OS: %s", os_type)
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
            command = [systemctl_cmd]
            if not system:
                command.append("--user")
            command.extend(["is-enabled", WEB_SERVICE_SYSTEMD_NAME])
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
            is_enabled = process.returncode == 0 and process.stdout.strip() == "enabled"
            logger.debug(
                "Web UI service '%s' enabled status: %s -> %s",
                WEB_SERVICE_SYSTEMD_NAME,
                process.stdout.strip(),
                is_enabled,
            )
            return is_enabled
        except Exception as e:
            log_operation_error(
                logger, "Error checking Web UI systemd enabled status: %s", e, error=e
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
                "Web UI service '%s' auto_start state from qc: %s",
                WEB_SERVICE_WINDOWS_NAME_INTERNAL,
                is_auto_start,
            )
            return is_auto_start
        except subprocess.CalledProcessError:
            logger.debug(
                "Web UI service '%s' not found or error during qc.",
                WEB_SERVICE_WINDOWS_NAME_INTERNAL,
            )
            return False
        except FileNotFoundError:
            logger.warning("`sc.exe` command not found unexpectedly.")
            return False
        except Exception as e:
            log_operation_error(
                logger,
                "Error checking Web UI Windows service enabled status: %s",
                e,
                error=e,
            )
            return False
    else:
        logger.debug("Web UI service enabled check not supported on OS: %s", os_type)
        return False
