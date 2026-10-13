"""
Standalone functions for managing the Web UI system service.

This module provides functions to interface with the operating system's service
manager (systemd, Windows Services) to control the Bedrock Server Manager Web UI service.
"""

import logging
import os
import platform
import re
import shlex
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
    DependencyUnavailableError,
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


def _web_service_command(
    config_dir: str | None, data_dir: str, *, windows: bool = False
) -> str:
    args = [sys.executable, "-m", "bedrock_server_manager"]
    if config_dir is not None:
        args.extend(["--config-dir", config_dir])
    args.extend(["--data-dir", data_dir])
    if windows:
        args.extend(["service", "_run-web", WEB_SERVICE_WINDOWS_NAME_INTERNAL])
        return subprocess.list2cmdline(args)
    args.extend(["web", "start", "--mode", "direct"])
    return shlex.join(args).replace("%", "%%")


def create_web_service_file(  # noqa: C901
    app_data_dir: str,
    system: bool = False,
    username: Optional[str] = None,
    password: Optional[str] = None,
    config_dir: str | None = None,
) -> None:
    """Creates or updates the system service file/entry for the Web UI."""
    os_type = platform.system()
    start_command = _web_service_command(config_dir, app_data_dir)

    if os_type == "Linux":
        _ensure_linux_for_web_service("create_web_service_file")
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
                timeout_stop_sec=180,
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
            DependencyUnavailableError,
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

        windows_service_binpath_command = _web_service_command(
            config_dir, app_data_dir, windows=True
        )

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
            DependencyUnavailableError,
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


def _query_web_service_state(*, enabled: bool, system: bool) -> bool:
    """Distinguish known negative service states from failed status queries."""
    os_type = platform.system()
    if os_type == "Linux":
        executable = shutil.which("systemctl")
        if not executable:
            raise DependencyUnavailableError("systemctl is unavailable.")
        command = [executable]
        if not system:
            command.append("--user")
        command.extend(
            ["is-enabled" if enabled else "is-active", WEB_SERVICE_SYSTEMD_NAME]
        )
        try:
            process = subprocess.run(
                command, capture_output=True, text=True, check=False, timeout=10
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise DependencyUnavailableError("Service status query failed.") from error
        state = process.stdout.strip()
        states = (
            {
                "enabled",
                "enabled-runtime",
                "linked",
                "linked-runtime",
                "alias",
                "static",
                "indirect",
                "generated",
                "transient",
                "disabled",
                "masked",
                "masked-runtime",
                "not-found",
            }
            if enabled
            else {
                "active",
                "inactive",
                "failed",
                "activating",
                "deactivating",
                "reloading",
                "refreshing",
                "maintenance",
                "not-found",
            }
        )
        if state not in states or process.returncode not in {0, 1, 3, 4}:
            raise DependencyUnavailableError("Service status could not be determined.")
        positive = "enabled" if enabled else "active"
        if state == positive and process.returncode != 0:
            raise DependencyUnavailableError(
                "Service status query returned conflicting results."
            )
        return process.returncode == 0 and state == positive
    if os_type == "Windows":
        executable = shutil.which("sc.exe")
        if not executable:
            raise DependencyUnavailableError("sc.exe is unavailable.")
        try:
            result = subprocess.check_output(
                [
                    executable,
                    "qc" if enabled else "query",
                    WEB_SERVICE_WINDOWS_NAME_INTERNAL,
                ],
                text=True,
                stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=10,
            )
        except subprocess.CalledProcessError as error:
            if error.returncode == 1060:
                return False
            raise DependencyUnavailableError("Service status query failed.") from error
        except (OSError, subprocess.SubprocessError) as error:
            raise DependencyUnavailableError("Service status query failed.") from error
        field = "START_TYPE" if enabled else "STATE"
        match = re.search(rf"{field}\s*:\s*\d+\s+(\w+)", result)
        states = (
            {"BOOT_START", "SYSTEM_START", "AUTO_START", "DEMAND_START", "DISABLED"}
            if enabled
            else {
                "STOPPED",
                "START_PENDING",
                "STOP_PENDING",
                "RUNNING",
                "CONTINUE_PENDING",
                "PAUSE_PENDING",
                "PAUSED",
            }
        )
        if match is None or match.group(1) not in states:
            raise DependencyUnavailableError("Service status could not be determined.")
        return match.group(1) == ("AUTO_START" if enabled else "RUNNING")
    raise DependencyUnavailableError(f"Service status is unsupported on {os_type}.")


def is_web_service_active(system: bool = False) -> bool:
    """Return a verified active state, or raise if the service manager is unavailable."""
    return _query_web_service_state(enabled=False, system=system)


def is_web_service_enabled(system: bool = False) -> bool:
    """Return a verified enabled state, or raise if the service manager is unavailable."""
    return _query_web_service_state(enabled=True, system=system)
