# bedrock_server_manager/api/task_scheduler.py
"""
Provides API functions for managing OS-level scheduled tasks.

This module offers a platform-agnostic interface for creating, querying,
modifying, and deleting scheduled tasks related to Bedrock server automation.
It achieves this by dispatching calls to OS-specific scheduler implementations
found in the :mod:`~bedrock_server_manager.core.system.task_scheduler` module,
primarily using instances of
:class:`~bedrock_server_manager.core.system.task_scheduler.LinuxTaskScheduler`
for cron jobs on Linux, and
:class:`~bedrock_server_manager.core.system.task_scheduler.WindowsTaskScheduler`
for Scheduled Tasks on Windows.

Key functionalities include:
    - **Linux (Cron Jobs):**
        - Retrieving server-specific cron jobs (:func:`~.get_server_cron_jobs`).
        - Formatting cron jobs for display (:func:`~.get_cron_jobs_table`).
        - Adding (:func:`~.add_cron_job`), modifying (:func:`~.modify_cron_job`),
          and deleting (:func:`~.delete_cron_job`) cron entries.
    - **Windows (Scheduled Tasks):**
        - Retrieving server-specific task names (:func:`~.get_server_task_names`)
          and detailed information (:func:`~.get_windows_task_info`).
        - Creating (:func:`~.create_windows_task`), modifying
          (:func:`~.modify_windows_task`), and deleting
          (:func:`~.delete_windows_task`) scheduled tasks via XML definitions.
    - **Utility:**
        - Generating standardized task names (:func:`~.create_task_name`).

The functions in this module are intended for internal use by higher-level
application components (e.g., web UI, CLI) and are not directly exposed
to the plugin system. They typically return dictionaries indicating the status
and outcome of operations.
"""

import os
import re
import logging
from typing import Dict, List, Optional, Any

# Local imports
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.utils.general import get_timestamp
from bedrock_server_manager.core.system import task_scheduler as core_task
from bedrock_server_manager.error import (
    BSMError,
    MissingArgumentError,
    UserInputError,
    FileOperationError,
    SystemError,
    InvalidServerNameError,
)

logger = logging.getLogger(__name__)

# --- Initialize the appropriate scheduler for the current OS ---
scheduler = core_task.get_task_scheduler()


# --- Linux Cron Functions ---


def get_server_cron_jobs(server_name: str) -> Dict[str, Any]:
    """
    Retrieves cron jobs related to a specific server from the user's crontab.
    (Linux-specific)

    Calls the `get_server_cron_jobs` method of the active
    :class:`~bedrock_server_manager.core.system.task_scheduler.LinuxTaskScheduler` instance.

    Args:
        server_name (str): The name of the Bedrock server. Cron jobs containing
            ``--server "<server_name>"`` in their command will be matched.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "cron_jobs": List[str]}`` where
        `cron_jobs` is a list of raw cron job strings.
        On error (e.g., not Linux, `crontab` command issues):
        ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        SystemError: If executing ``crontab -l`` fails.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    if not isinstance(scheduler, core_task.LinuxTaskScheduler):
        msg = "Cron job operations are only supported on Linux."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    logger.debug(f"API: Retrieving cron jobs for server '{server_name}'...")
    try:
        cron_jobs_list = scheduler.get_server_cron_jobs(server_name)
        return {"status": "success", "cron_jobs": cron_jobs_list}
    except BSMError as e:
        logger.error(
            f"Failed to retrieve cron jobs for '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Failed to retrieve cron jobs: {e}"}


def get_cron_jobs_table(cron_jobs: List[str]) -> Dict[str, Any]:
    """
    Formats a list of raw cron job strings into structured dictionaries for display.
    (Linux-specific)

    Calls the `get_cron_jobs_table` method of the active
    :class:`~bedrock_server_manager.core.system.task_scheduler.LinuxTaskScheduler` instance.

    Args:
        cron_jobs (List[str]): A list of raw cron job strings, typically obtained
            from :func:`~.get_server_cron_jobs`.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "table_data": List[CronJobDict]}``
        where each ``CronJobDict`` contains keys like "minute", "hour",
        "day_of_month", "month", "day_of_week", "command", "command_display",
        and "schedule_time".
        On error (e.g., not Linux): ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        TypeError: If `cron_jobs` is not a list.
    """
    if not isinstance(cron_jobs, list):
        raise TypeError("Input 'cron_jobs' must be a list.")

    if not isinstance(scheduler, core_task.LinuxTaskScheduler):
        msg = "Cron job operations are only supported on Linux."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    logger.debug(f"API: Formatting {len(cron_jobs)} cron jobs for table display...")
    try:
        table_data = scheduler.get_cron_jobs_table(cron_jobs)
        return {"status": "success", "table_data": table_data}
    except Exception as e:
        logger.error(
            f"Error formatting cron job list into table data: {e}", exc_info=True
        )
        return {"status": "error", "message": f"Error formatting cron job table: {e}"}


def add_cron_job(cron_job_string: str) -> Dict[str, str]:
    """
    Adds a new job line to the user's crontab.
    (Linux-specific)

    Calls the `add_job` method of the active
    :class:`~bedrock_server_manager.core.system.task_scheduler.LinuxTaskScheduler` instance.
    The core method avoids adding duplicate entries.

    Args:
        cron_job_string (str): The full cron job line to add
            (e.g., ``"0 2 * * * /path/to/command --arg"``).

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        On success: ``{"status": "success", "message": "Cron job added successfully."}``
        On error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        MissingArgumentError: If `cron_job_string` is empty.
        SystemError: If reading/writing the crontab fails.
    """
    if not cron_job_string or not cron_job_string.strip():
        raise MissingArgumentError("Cron job string cannot be empty.")

    if not isinstance(scheduler, core_task.LinuxTaskScheduler):
        msg = "Cron job operations are only supported on Linux."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    logger.info(f"API: Attempting to add cron job: '{cron_job_string}'")
    try:
        scheduler.add_job(cron_job_string.strip())
        return {"status": "success", "message": "Cron job added successfully."}
    except BSMError as e:
        logger.error(f"Failed to add cron job '{cron_job_string}': {e}", exc_info=True)
        return {"status": "error", "message": f"Error adding cron job: {e}"}


def modify_cron_job(
    old_cron_job_string: str, new_cron_job_string: str
) -> Dict[str, str]:
    """
    Modifies an existing cron job by replacing the old line with the new line.
    (Linux-specific)

    Calls the `update_job` method of the active
    :class:`~bedrock_server_manager.core.system.task_scheduler.LinuxTaskScheduler` instance.

    Args:
        old_cron_job_string (str): The exact existing cron job line to be replaced.
        new_cron_job_string (str): The new cron job line to substitute.

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        On success: ``{"status": "success", "message": "Cron job modified successfully."}``
        If old and new strings are identical: ``{"status": "success", "message": "No modification needed..."}``
        On error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        MissingArgumentError: If either cron job string is empty.
        UserInputError: If `old_cron_job_string` is not found in the crontab.
        SystemError: If reading/writing the crontab fails.
    """
    if not old_cron_job_string or not old_cron_job_string.strip():
        raise MissingArgumentError("Old cron job string cannot be empty.")
    if not new_cron_job_string or not new_cron_job_string.strip():
        raise MissingArgumentError("New cron job string cannot be empty.")

    if not isinstance(scheduler, core_task.LinuxTaskScheduler):
        msg = "Cron job operations are only supported on Linux."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    old_strip, new_strip = old_cron_job_string.strip(), new_cron_job_string.strip()
    if old_strip == new_strip:
        return {
            "status": "success",
            "message": "No modification needed, jobs are identical.",
        }

    logger.info(
        f"API: Attempting to modify cron job: Replace '{old_strip}' with '{new_strip}'"
    )
    try:
        scheduler.update_job(old_strip, new_strip)
        return {"status": "success", "message": "Cron job modified successfully."}
    except BSMError as e:
        logger.error(f"Failed to modify cron job: {e}", exc_info=True)
        return {"status": "error", "message": f"Error modifying cron job: {e}"}


def delete_cron_job(cron_job_string: str) -> Dict[str, str]:
    """
    Deletes a specific job line from the user's crontab.
    (Linux-specific)

    Calls the `delete_job` method of the active
    :class:`~bedrock_server_manager.core.system.task_scheduler.LinuxTaskScheduler` instance.
    If the specified job string is not found, the operation is considered successful
    (idempotent delete).

    Args:
        cron_job_string (str): The exact cron job line to delete.

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        On success: ``{"status": "success", "message": "Cron job deleted successfully (if it existed)."}``
        On error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        MissingArgumentError: If `cron_job_string` is empty.
        SystemError: If reading/writing the crontab fails.
    """
    if not cron_job_string or not cron_job_string.strip():
        raise MissingArgumentError("Cron job string to delete cannot be empty.")

    if not isinstance(scheduler, core_task.LinuxTaskScheduler):
        msg = "Cron job operations are only supported on Linux."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    cron_strip = cron_job_string.strip()
    logger.info(f"API: Attempting to delete cron job: '{cron_strip}'")
    try:
        scheduler.delete_job(cron_strip)
        return {
            "status": "success",
            "message": "Cron job deleted successfully (if it existed).",
        }
    except BSMError as e:
        logger.error(f"Failed to delete cron job '{cron_strip}': {e}", exc_info=True)
        return {"status": "error", "message": f"Error deleting cron job: {e}"}


# --- Windows Task Scheduler Functions ---


def get_server_task_names(
    server_name: str, config_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieves scheduled task names and their XML file paths associated with a specific server.
    (Windows-specific)

    Calls the `get_server_task_names` method of the active
    :class:`~bedrock_server_manager.core.system.task_scheduler.WindowsTaskScheduler` instance.
    This involves scanning the server's configuration subdirectory for ``.xml``
    task definition files and parsing the task URI from each.

    Args:
        server_name (str): The name of the Bedrock server.
        config_dir (Optional[str], optional): The base application configuration
            directory. If ``None``, uses the globally configured settings.config_dir.
            Defaults to ``None``.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "task_names": List[Tuple[str, str]]}``
        where each tuple is (task_name_in_scheduler, xml_file_path).
        On error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        MissingArgumentError: If `server_name` is empty.
        FileOperationError: If `config_dir` is invalid or reading the task directory fails.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    if not isinstance(scheduler, core_task.WindowsTaskScheduler):
        msg = "Windows Task Scheduler operations are only supported on Windows."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    logger.debug(f"API: Getting Windows task names for server '{server_name}'...")
    try:
        effective_config_dir = config_dir or getattr(settings, "config_dir", None)
        if not effective_config_dir:
            raise FileOperationError(
                "Base configuration directory is not set or available."
            )

        task_name_list = scheduler.get_server_task_names(
            server_name, effective_config_dir
        )
        return {"status": "success", "task_names": task_name_list}
    except BSMError as e:
        logger.error(
            f"Failed to get task names for server '{server_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Error getting task names: {e}"}


def get_windows_task_info(task_names: List[str]) -> Dict[str, Any]:
    """
    Retrieves detailed information for a list of Windows tasks.
    (Windows-specific)

    Calls the `get_task_info` method of the active
    :class:`~bedrock_server_manager.core.system.task_scheduler.WindowsTaskScheduler` instance.
    This involves querying each task's XML definition from Task Scheduler and parsing it.

    Args:
        task_names (List[str]): A list of task names (typically including their
            path in Task Scheduler, e.g., ``"\\MyTasks\\MyServerBackup"``) to query.

    Returns:
        Dict[str, Any]: A dictionary with the operation result.
        On success: ``{"status": "success", "task_info": List[TaskInfoDict]}``
        where each ``TaskInfoDict`` contains "task_name", "command", and "schedule".
        Tasks not found or those causing parsing errors are omitted from results.
        On error (e.g., not Windows): ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        TypeError: If `task_names` is not a list.
        SystemError: If ``schtasks`` command fails for reasons other than task not found.
    """
    if not isinstance(task_names, list):
        raise TypeError("Input 'task_names' must be a list.")

    if not isinstance(scheduler, core_task.WindowsTaskScheduler):
        msg = "Windows Task Scheduler operations are only supported on Windows."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    logger.debug(f"API: Getting detailed info for Windows tasks: {task_names}")
    try:
        task_info_list = scheduler.get_task_info(task_names)
        return {"status": "success", "task_info": task_info_list}
    except BSMError as e:
        logger.error(f"Failed to get Windows task info: {e}", exc_info=True)
        return {"status": "error", "message": f"Error getting task info: {e}"}


def create_windows_task(
    server_name: str,
    command: str,
    command_args: str,
    task_name: str,
    triggers: List[Dict[str, Any]],
    config_dir: Optional[str] = None,
) -> Dict[str, str]:
    """
    Creates a new Windows scheduled task by generating and importing an XML definition.
    (Windows-specific)

    This function first calls the `create_task_xml` method of the active
    :class:`~bedrock_server_manager.core.system.task_scheduler.WindowsTaskScheduler`
    instance to generate an XML task definition file. It then calls the
    `import_task_from_xml` method to register this task with Windows Task Scheduler.

    Args:
        server_name (str): The name of the Bedrock server this task is associated with.
        command (str): The primary command action for the task (e.g., "backup").
        command_args (str): Additional arguments for the command.
        task_name (str): The desired path and name for the task in Task Scheduler
            (e.g., ``"\\MyApplication\\ServerBackup"``).
        triggers (List[Dict[str, Any]]): A list of trigger definitions. Each dict
            must have a "type" (e.g., "Daily", "Weekly") and type-specific
            parameters like "start" (ISO datetime), "days" (for weekly/monthly),
            "months" (for monthly), "interval".
        config_dir (Optional[str], optional): Base application configuration directory
            for storing the generated XML file. Defaults to global setting.

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        On success: ``{"status": "success", "message": "Windows task '<task_name>' created successfully."}``
        On error: ``{"status": "error", "message": "<error_message>"}``.

    Raises:
        MissingArgumentError: If required arguments are empty.
        TypeError: If `triggers` is not a list.
        FileOperationError: If XML file creation or `config_dir` access fails.
        AppFileNotFoundError: If the main application script (EXPATH) is not found.
        UserInputError: If trigger data is invalid.
        PermissionsError: If `schtasks` fails due to insufficient privileges.
        SystemError: For other `schtasks` command failures.
    """
    if not all([server_name, command, task_name]):
        raise MissingArgumentError("Server name, command, and task name are required.")
    if not isinstance(triggers, list):
        raise TypeError("Triggers must be a list.")

    if not isinstance(scheduler, core_task.WindowsTaskScheduler):
        msg = "Windows Task operations are only supported on Windows."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    logger.info(
        f"API: Creating Windows task '{task_name}' for server '{server_name}'..."
    )
    try:
        effective_config_dir = config_dir or getattr(settings, "config_dir", None)
        if not effective_config_dir:
            raise FileOperationError(
                "Base configuration directory is not set or available."
            )

        xml_path = scheduler.create_task_xml(
            server_name,
            command,
            command_args,
            task_name,
            effective_config_dir,
            triggers,
        )
        scheduler.import_task_from_xml(xml_path, task_name)

        return {
            "status": "success",
            "message": f"Windows task '{task_name}' created successfully.",
        }
    except BSMError as e:
        logger.error(f"Failed to create Windows task '{task_name}': {e}", exc_info=True)
        return {"status": "error", "message": f"Error creating task: {e}"}


def modify_windows_task(
    old_task_name: str,
    server_name: str,
    command: str,
    command_args: str,
    new_task_name: str,
    triggers: List[Dict[str, Any]],
    config_dir: Optional[str] = None,
) -> Dict[str, str]:
    """
    Modifies an existing Windows task by deleting the old one and creating a new one.
    (Windows-specific)

    This function first attempts to delete the existing task specified by
    `old_task_name` using the `delete_task` method of the active
    :class:`~bedrock_server_manager.core.system.task_scheduler.WindowsTaskScheduler`
    instance. It also attempts to remove the old task's XML definition file.
    Then, it proceeds to create a new task using :func:`~.create_windows_task`
    with the new parameters.

    Args:
        old_task_name (str): The name/path of the existing task in Task Scheduler to be replaced.
        server_name (str): The name of the Bedrock server for the new task.
        command (str): The primary command action for the new task.
        command_args (str): Additional arguments for the new task's command.
        new_task_name (str): The name/path for the new task in Task Scheduler.
        triggers (List[Dict[str, Any]]): Trigger definitions for the new task.
        config_dir (Optional[str], optional): Base config directory for the new task's XML.
            Defaults to global setting.

    Returns:
        Dict[str, str]: A dictionary with the operation result, reflecting the
        outcome of the `create_windows_task` call.
        On success: ``{"status": "success", "message": "Windows task '<new_task_name>' created successfully."}``
        On error: ``{"status": "error", "message": "<error_message_from_create_or_modify>"}``.

    Raises:
        MissingArgumentError: If required arguments are empty.
        TypeError: If `triggers` is not a list.
        BSMError: Propagates errors from the underlying delete or create operations,
            including `FileOperationError`, `AppFileNotFoundError`, `UserInputError`,
            `PermissionsError`, or `SystemError`.
    """
    if not all([old_task_name, server_name, command, new_task_name]):
        raise MissingArgumentError(
            "Old/new task names, server name, and command are required."
        )
    if not isinstance(triggers, list):
        raise TypeError("Triggers must be a list.")

    if not isinstance(scheduler, core_task.WindowsTaskScheduler):
        msg = "Windows Task operations are only supported on Windows."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    logger.info(
        f"API: Modifying Windows task '{old_task_name}' to '{new_task_name}'..."
    )
    try:
        effective_config_dir = config_dir or getattr(settings, "config_dir", None)
        if not effective_config_dir:
            raise FileOperationError(
                "Base configuration directory is not set or available."
            )

        # 1. Delete the old task
        scheduler.delete_task(old_task_name)

        # 2. Delete the old XML file
        old_safe_filename = re.sub(r'[\\/*?:"<>|]', "_", old_task_name) + ".xml"
        old_xml_path = os.path.join(
            effective_config_dir, server_name, old_safe_filename
        )
        if os.path.isfile(old_xml_path):
            try:
                os.remove(old_xml_path)
            except OSError as e:
                logger.warning(
                    f"Could not delete old task XML '{old_xml_path}': {e}. Proceeding."
                )

        # 3. Create the new task
        return create_windows_task(
            server_name,
            command,
            command_args,
            new_task_name,
            triggers,
            effective_config_dir,
        )
    except BSMError as e:
        logger.error(
            f"Failed to modify Windows task '{old_task_name}': {e}", exc_info=True
        )
        return {"status": "error", "message": f"Error modifying task: {e}"}


def delete_windows_task(task_name: str, task_file_path: str) -> Dict[str, str]:
    """
    Deletes a Windows scheduled task and its associated definition XML file.
    (Windows-specific)

    This function first attempts to delete the task from Windows Task Scheduler
    using the `delete_task` method of the active
    :class:`~bedrock_server_manager.core.system.task_scheduler.WindowsTaskScheduler`
    instance. Then, it attempts to delete the local XML definition file specified
    by `task_file_path` using ``os.remove``.

    Args:
        task_name (str): The name/path of the task in Task Scheduler to delete.
        task_file_path (str): The absolute path to the local XML task definition
            file to be deleted.

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        If both task and file are deleted (or were already gone):
        ``{"status": "success", "message": "Task '<task_name>' and its definition file deleted successfully."}``
        If errors occur: ``{"status": "error", "message": "Task deletion completed with errors: <details>"}``.

    Raises:
        MissingArgumentError: If `task_name` or `task_file_path` are empty.
        PermissionsError: If `schtasks` or file deletion fails due to insufficient privileges.
        SystemError: For other `schtasks` command failures.
    """
    if not task_name:
        raise MissingArgumentError("Task name cannot be empty.")
    if not task_file_path:
        raise MissingArgumentError("Task file path cannot be empty.")

    if not isinstance(scheduler, core_task.WindowsTaskScheduler):
        msg = "Windows Task operations are only supported on Windows."
        logger.warning(msg)
        return {"status": "error", "message": msg}

    logger.info(
        f"API: Deleting Windows task '{task_name}' and file '{task_file_path}'..."
    )
    errors = []

    try:
        scheduler.delete_task(task_name)
    except BSMError as e:
        errors.append(f"Scheduler deletion failed ({e})")
        logger.error(
            f"Failed to delete task '{task_name}' from Task Scheduler: {e}",
            exc_info=True,
        )

    if os.path.isfile(task_file_path):
        try:
            os.remove(task_file_path)
        except OSError as e:
            errors.append(f"XML file deletion failed ({e})")
            logger.error(
                f"Failed to delete task XML file '{task_file_path}': {e}", exc_info=True
            )

    if errors:
        return {
            "status": "error",
            "message": f"Task deletion completed with errors: {'; '.join(errors)}",
        }
    return {
        "status": "success",
        "message": f"Task '{task_name}' and its definition file deleted successfully.",
    }


# --- Platform-Agnostic Helper Functions ---


def create_task_name(server_name: str, command_args: str) -> str:
    """
    Generates a unique, filesystem-safe task name.

    Constructs a task name typically in the format:
    ``bedrock_<server_name>_<sanitized_command_args>_<timestamp>``.
    The `command_args` are cleaned by removing ``--server <name>`` parts and
    sanitizing remaining characters to be filesystem-safe.

    Args:
        server_name (str): The name of the server associated with the task.
        command_args (str): The command arguments string that the task will execute.

    Returns:
        str: A generated unique and safe task name.

    Raises:
        MissingArgumentError: If `server_name` is empty.
    """
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")

    cleaned_args = re.sub(r"--server\s+\S+\s*", "", command_args).strip()
    sanitized = re.sub(r'[\\/*?:"<>|\s\-\.]+', "_", cleaned_args).strip("_")[:30]
    timestamp = get_timestamp()

    task_name = f"bedrock_{server_name}_{sanitized}_{timestamp}"
    return task_name.replace("\\", "_")
