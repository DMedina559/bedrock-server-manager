# bedrock_server_manager/core/system/linux.py
"""Linux systemd service definition and autostart helpers."""

import logging
import os
import platform
import shutil
import subprocess
from typing import Optional

from ...error import (
    AppFileNotFoundError,
    CommandNotFoundError,
    FileOperationError,
    MissingArgumentError,
    SystemError,
)

logger = logging.getLogger(__name__)


# --- Systemd Service Management ---
def get_systemd_service_file_path(service_name_full: str, system: bool = False) -> str:
    """Resolve a user or system unit path, adding the ``.service`` suffix if needed."""
    if not isinstance(service_name_full, str) or not service_name_full:
        raise MissingArgumentError(
            "Full service name cannot be empty and must be a string."
        )

    name_to_use = (
        service_name_full
        if service_name_full.endswith(".service")
        else f"{service_name_full}.service"
    )

    if system:
        return os.path.join("/etc/systemd/system", name_to_use)
    else:
        # User service files are typically located in ~/.config/systemd/user/
        return os.path.join(
            os.path.expanduser("~"), ".config", "systemd", "user", name_to_use
        )


def check_service_exists(service_name_full: str, system: bool = False) -> bool:
    """Return whether the selected user or system unit file exists."""
    if platform.system() != "Linux":
        logger.debug(
            "check_service_exists: Not Linux. Systemd check not applicable, returning False."
        )
        return False
    if not isinstance(service_name_full, str) or not service_name_full:
        raise MissingArgumentError(
            "Full service name cannot be empty and must be a string for service file check."
        )

    service_file_path = get_systemd_service_file_path(service_name_full, system=system)
    logger.debug("Checking for systemd service file existence: '%s'", service_file_path)
    exists = os.path.isfile(service_file_path)
    logger.debug("Service file '%s' exists: %s", service_file_path, exists)
    return exists


def create_systemd_service_file(  # noqa: C901
    service_name_full: str,
    description: str,
    working_directory: str,
    exec_start_command: str,
    exec_stop_command: Optional[str] = None,
    exec_start_pre_command: Optional[str] = None,
    service_type: str = "forking",
    restart_policy: str = "on-failure",
    restart_sec: int = 10,
    timeout_stop_sec: int | None = None,
    after_targets: str = "network.target",
    system: bool = False,
) -> None:
    """Write a user or system unit and reload the systemd daemon.

    Optional start/stop commands and restart policy are preserved; timeout values are
    seconds. Filesystem and service-manager failures propagate.
    """
    if platform.system() != "Linux":
        logger.warning(
            "Generic systemd service creation skipped: Not Linux. Service: '%s'",
            service_name_full,
        )
        return

    if not all([service_name_full, description, working_directory, exec_start_command]):
        raise MissingArgumentError(
            "service_name_full, description, working_directory, and exec_start_command are required."
        )
    if not os.path.isdir(working_directory):
        raise AppFileNotFoundError(working_directory, "WorkingDirectory")

    service_file_path = get_systemd_service_file_path(service_name_full, system=system)
    service_dir = os.path.dirname(service_file_path)

    logger.debug(
        "Creating/Updating generic systemd service file: '%s'", service_file_path
    )

    try:
        os.makedirs(service_dir, exist_ok=True)
    except OSError as e:
        raise FileOperationError(
            f"Failed to create systemd directory '{service_dir}': {e}"
        ) from e

    # Build the service file content.
    exec_start_pre_line = (
        f"ExecStartPre={exec_start_pre_command}" if exec_start_pre_command else ""
    )
    exec_stop_line = f"ExecStop={exec_stop_command}" if exec_stop_command else ""
    user_line = f"User={os.getlogin()}" if system else ""

    service_content = f"""[Unit]
Description={description}
After={after_targets}

[Service]
{user_line}
Type={service_type}
WorkingDirectory={working_directory}
{exec_start_pre_line}
ExecStart={exec_start_command}
{exec_stop_line}
Restart={restart_policy}
RestartSec={restart_sec}s
{f"TimeoutStopSec={timeout_stop_sec}s" if timeout_stop_sec is not None else ""}

[Install]
WantedBy=default.target
"""
    # Remove empty lines that might occur if optional commands are not provided.
    service_content = "\n".join(
        [line for line in service_content.splitlines() if line.strip()]
    )

    try:
        with open(service_file_path, "w", encoding="utf-8") as f:
            f.write(service_content)
        logger.debug(
            "Successfully wrote generic systemd service file: %s", service_file_path
        )
    except OSError as e:
        raise FileOperationError(
            f"Failed to write service file '{service_file_path}': {e}"
        ) from e

    # Reload systemd daemon to recognize the new/updated file.
    systemctl_cmd = shutil.which("systemctl")
    if not systemctl_cmd:
        raise CommandNotFoundError("systemctl")
    try:
        # Conditionally build the command to avoid empty strings for system-wide services.
        command = [systemctl_cmd]
        if not system:
            command.append("--user")
        command.append("daemon-reload")

        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        logger.debug(
            "Systemd daemon reloaded successfully for service '%s'.", service_name_full
        )
    except subprocess.CalledProcessError as e:
        raise SystemError(f"Failed to reload systemd daemon. Error: {e.stderr}") from e


def enable_systemd_service(  # noqa: C901
    service_name_full: str, system: bool = False
) -> None:
    """Enable the selected user or system unit for autostart."""
    if platform.system() != "Linux":
        logger.debug(
            "enable_systemd_service: Not Linux. Systemd operation not applicable."
        )
        return
    if not isinstance(service_name_full, str) or not service_name_full:
        raise MissingArgumentError(
            "Full service name cannot be empty and must be a string."
        )

    name_to_use = (
        service_name_full
        if service_name_full.endswith(".service")
        else f"{service_name_full}.service"
    )
    logger.debug("Attempting to enable systemd service '%s'...", name_to_use)

    systemctl_cmd = shutil.which("systemctl")
    if not systemctl_cmd:
        raise CommandNotFoundError("systemctl")

    if not check_service_exists(name_to_use, system=system):
        raise SystemError(
            f"Cannot enable: Systemd service file for '{name_to_use}' does not exist. "
            "Ensure the service file has been created and daemon-reloaded."
        )

    # Check if already enabled to avoid unnecessary calls.
    try:
        command = [systemctl_cmd]
        if not system:
            command.append("--user")
        command.extend(["is-enabled", name_to_use])
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,  # Don't raise for non-zero exit if not enabled
        )
        status_output = process.stdout.strip().lower()
        logger.debug(
            "'systemctl is-enabled %s' output: '%s', return code: %s",
            name_to_use,
            status_output,
            process.returncode,
        )
        # "enabled" means it's enabled. Other statuses like "disabled", "static", "masked"
        # or an empty output with non-zero exit code mean it's not actively enabled.
        if status_output == "enabled":
            logger.debug("Service '%s' is already enabled.", name_to_use)
            return
    except Exception as e:
        logger.warning(
            "Could not reliably determine if service '%s' is enabled: %s. Attempting to enable it anyway.",
            name_to_use,
            e,
            exc_info=True,
        )

    try:
        command = [systemctl_cmd]
        if not system:
            command.append("--user")
        command.extend(["enable", name_to_use])
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("Systemd service '%s' enabled successfully.", name_to_use)
    except subprocess.CalledProcessError as e:
        raise SystemError(
            f"Failed to enable systemd service '{name_to_use}'. Error: {e.stderr.strip()}"
        ) from e


def disable_systemd_service(  # noqa: C901
    service_name_full: str, system: bool = False
) -> None:
    """Disable autostart for the selected user or system unit."""
    if platform.system() != "Linux":
        logger.debug(
            "disable_systemd_service: Not Linux. Systemd operation not applicable."
        )
        return
    if not isinstance(service_name_full, str) or not service_name_full:
        raise MissingArgumentError(
            "Full service name cannot be empty and must be a string."
        )

    name_to_use = (
        service_name_full
        if service_name_full.endswith(".service")
        else f"{service_name_full}.service"
    )
    logger.debug("Attempting to disable systemd service '%s'...", name_to_use)

    systemctl_cmd = shutil.which("systemctl")
    if not systemctl_cmd:
        raise CommandNotFoundError("systemctl")

    if not check_service_exists(name_to_use, system=system):
        logger.debug(
            "Service file for '%s' does not exist. Assuming already disabled or removed.",
            name_to_use,
        )
        return

    # Check if already disabled or not in an "enabled" state.
    try:
        command = [systemctl_cmd]
        if not system:
            command.append("--user")
        command.extend(["is-enabled", name_to_use])
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,  # Don't raise for non-zero exit
        )
        status_output = process.stdout.strip().lower()
        logger.debug(
            "'systemctl is-enabled %s' output: '%s', return code: %s",
            name_to_use,
            status_output,
            process.returncode,
        )
        # If not "enabled", it's effectively disabled for auto-start or in a state
        # where 'disable' might not apply or is redundant.
        if status_output != "enabled":
            logger.debug(
                "Service '%s' is already in a non-enabled state ('%s'). No action needed for disable.",
                name_to_use,
                status_output,
            )
            return
    except Exception as e:
        logger.warning(
            "Could not reliably determine if service '%s' is enabled: %s. Attempting to disable it anyway.",
            name_to_use,
            e,
            exc_info=True,
        )

    try:
        command = [systemctl_cmd]
        if not system:
            command.append("--user")
        command.extend(["disable", name_to_use])
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("Systemd service '%s' disabled successfully.", name_to_use)
    except subprocess.CalledProcessError as e:
        stderr_lower = (e.stderr or "").strip().lower()
        # It's not an error if the service is static or masked, as 'disable' doesn't apply.
        if "static" in stderr_lower or "masked" in stderr_lower:
            logger.info(
                "Service '%s' is %s. It cannot be disabled via 'systemctl disable' command.",
                name_to_use,
                stderr_lower.split()[-1],
            )
            return
        raise SystemError(
            f"Failed to disable systemd service '{name_to_use}'. Error: {e.stderr.strip()}"
        ) from e
