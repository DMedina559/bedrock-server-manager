# bedrock_server_manager/core/system/task_scheduler.py
"""Provides a platform-agnostic interface for OS-level task scheduling.

This module abstracts the complexities of creating, modifying, and deleting
scheduled tasks (e.g., cron jobs on Linux, Scheduled Tasks on Windows) that
are used to automate Bedrock server operations like backups or restarts.

Key Components:

    - :func:`.get_task_scheduler`: A factory function that returns an instance of
      the appropriate OS-specific scheduler class.
    - :class:`.LinuxTaskScheduler`: Manages cron jobs on Linux systems. Requires
      the ``crontab`` command-line utility.
    - :class:`.WindowsTaskScheduler`: Manages Scheduled Tasks on Windows systems.
      Requires the ``schtasks`` command-line utility.

Each scheduler class provides methods to add, update, delete, and query
scheduled tasks relevant to Bedrock server instances managed by this application.
The module aims to provide a consistent API for these operations across
supported platforms.
"""

import platform
import os
import logging
import subprocess
import shutil
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
import xml.etree.ElementTree as ET
import re
from typing import Union

# Local application imports.
from bedrock_server_manager.config.const import EXPATH
from bedrock_server_manager.error import (
    CommandNotFoundError,
    SystemError,
    InvalidServerNameError,
    UserInputError,
    MissingArgumentError,
    FileOperationError,
    AppFileNotFoundError,
    PermissionsError,
)

logger = logging.getLogger(__name__)


def get_task_scheduler() -> Optional[Any]:
    """A factory function to get the appropriate task scheduler for the current OS.

    This function checks the current operating system using `platform.system()`.

        - If "Linux", it attempts to instantiate and return :class:`.LinuxTaskScheduler`.
        - If "Windows", it attempts to instantiate and return :class:`.WindowsTaskScheduler`.
        - For other operating systems, it logs a warning and returns ``None``.

    If the instantiation of an OS-specific scheduler fails (e.g., due to a
    :class:`~.error.CommandNotFoundError` if `crontab` or `schtasks` is
    missing), an error is logged, and ``None`` is returned, effectively disabling
    task scheduling features for that environment.

    Returns:
        Optional[Union[LinuxTaskScheduler, WindowsTaskScheduler]]: An instance of
        a platform-specific scheduler class (either :class:`.LinuxTaskScheduler`
        or :class:`.WindowsTaskScheduler`) if the OS is supported and the
        necessary prerequisites (like command-line tools) are met. Returns ``None``
        if the OS is unsupported or if prerequisites are missing.
    """
    system = platform.system()

    if system == "Linux":
        try:
            # Attempt to create a Linux scheduler, which checks for `crontab`.
            return LinuxTaskScheduler()
        except CommandNotFoundError:
            logger.error(
                "Linux system detected, but the 'crontab' command is missing. Scheduling will be disabled."
            )
            return None

    elif system == "Windows":
        try:
            # Attempt to create a Windows scheduler, which checks for `schtasks`.
            return WindowsTaskScheduler()
        except CommandNotFoundError:
            logger.error(
                "Windows system detected, but the 'schtasks' command is missing. Scheduling will be disabled."
            )
            return None

    else:
        logger.warning(
            f"Task scheduling is not supported on this operating system: {system}"
        )
        return None


class LinuxTaskScheduler:
    """Manages scheduled tasks (cron jobs) for Bedrock servers on Linux systems.

    This class provides an interface to interact with the user's crontab for
    scheduling automated tasks related to Bedrock servers. It allows adding,
    updating, deleting, and querying cron jobs that are tagged with a specific
    server name.

    All operations are performed by invoking the ``crontab`` command-line utility.
    The presence of this utility is checked upon instantiation.

    Internal helper methods are used for parsing cron lines, formatting command
    strings for display, and converting cron time fields to human-readable formats.

    Attributes:
        crontab_cmd (str): The absolute path to the `crontab` executable.
    """

    # A mapping to convert cron month numbers/abbreviations to full names.
    _CRON_MONTHS_MAP: Dict[str, str] = {
        "1": "January",
        "jan": "January",
        "january": "January",
        "2": "February",
        "feb": "February",
        "february": "February",
        "3": "March",
        "mar": "March",
        "march": "March",
        "4": "April",
        "apr": "April",
        "april": "April",
        "5": "May",
        "may": "May",
        "6": "June",
        "jun": "June",
        "june": "June",
        "7": "July",
        "jul": "July",
        "july": "July",
        "8": "August",
        "aug": "August",
        "august": "August",
        "9": "September",
        "sep": "September",
        "september": "September",
        "10": "October",
        "oct": "October",
        "october": "October",
        "11": "November",
        "nov": "November",
        "november": "November",
        "12": "December",
        "dec": "December",
        "december": "December",
    }
    # A mapping to convert cron day-of-week numbers/abbreviations to full names.
    _CRON_DAYS_MAP = {
        "0": "Sunday",
        "sun": "Sunday",
        "sunday": "Sunday",
        "1": "Monday",
        "mon": "Monday",
        "monday": "Monday",
        "2": "Tuesday",
        "tue": "Tuesday",
        "tuesday": "Tuesday",
        "3": "Wednesday",
        "wed": "Wednesday",
        "wednesday": "Wednesday",
        "4": "Thursday",
        "thu": "Thursday",
        "thursday": "Thursday",
        "5": "Friday",
        "fri": "Friday",
        "friday": "Friday",
        "6": "Saturday",
        "sat": "Saturday",
        "saturday": "Saturday",
        "7": "Sunday",  # Also map 7 to Sunday as some cron versions allow it.
    }

    def __init__(self) -> None:
        """Initializes the LinuxTaskScheduler.

        This constructor checks for the presence of the ``crontab`` command-line
        utility using ``shutil.which()``. If not found, it raises a
        :class:`~.error.CommandNotFoundError`.

        Raises:
            CommandNotFoundError: If the `crontab` command is not available in
                the system's PATH.
        """
        self.crontab_cmd: str = shutil.which("crontab")  # type: ignore
        if not self.crontab_cmd:
            logger.error("'crontab' command not found. Cannot manage cron jobs.")
            raise CommandNotFoundError("crontab")
        logger.debug(
            f"LinuxTaskScheduler initialized successfully with crontab: {self.crontab_cmd}"
        )

    def _get_cron_month_name(self, month_input: str) -> str:
        """Converts a cron month input (number or abbreviation) to its full month name.

        Args:
            month_input (str): The month value from a cron string (e.g., "1", "Jan", "january").

        Returns:
            str: The full name of the month (e.g., "January").

        Raises:
            UserInputError: If `month_input` is not a recognized month number,
                abbreviation, or name.
        """
        month_str = str(month_input).strip().lower()
        if month_str in self._CRON_MONTHS_MAP:
            return self._CRON_MONTHS_MAP[month_str]
        else:
            raise UserInputError(
                f"Invalid month value: '{month_input}'. Use 1-12 or name/abbreviation."
            )

    def _get_cron_dow_name(self, dow_input: str) -> str:
        """Converts a cron day-of-week input (number or abbreviation) to its full day name.

        Note: Cron's day-of-week can be 0-7, where both 0 and 7 represent Sunday.
        This function standardizes 7 to 0 before lookup.

        Args:
            dow_input (str): The day-of-week value from a cron string (e.g., "0", "Sun", "sunday").

        Returns:
            str: The full name of the day (e.g., "Sunday").

        Raises:
            UserInputError: If `dow_input` is not a recognized day number,
                abbreviation, or name.
        """
        dow_str = str(dow_input).strip().lower()
        if dow_str == "7":  # Standardize 7 to 0 for Sunday for internal mapping.
            dow_str = "0"
        if dow_str in self._CRON_DAYS_MAP:
            return self._CRON_DAYS_MAP[dow_str]
        else:
            raise UserInputError(
                f"Invalid day-of-week value: '{dow_input}'. Use 0-6, 7, or name/abbreviation (Sun-Sat)."
            )

    @staticmethod
    def _parse_cron_line(line: str) -> Optional[Tuple[str, str, str, str, str, str]]:
        """Parses a standard cron job line into its six components.

        A cron line consists of five time/date fields followed by the command.
        This method splits the line accordingly.

        Args:
            line (str): A single line from a crontab.

        Returns:
            Optional[Tuple[str, str, str, str, str, str]]: A tuple containing
            (minute, hour, day_of_month, month, day_of_week, command_string)
            if parsing is successful. Returns ``None`` if the line does not
            conform to the expected structure (e.g., less than 6 parts).
        """
        parts = line.strip().split(maxsplit=5)
        if len(parts) == 6:
            return tuple(parts)
        else:
            logger.warning(
                f"Could not parse cron line (expected 6 parts, got {len(parts)}): '{line}'"
            )
            return None

    @staticmethod
    def _format_cron_command(command_string: str) -> str:
        """Formats the command part of a cron job for a more concise display.

        This method attempts to strip common prefixes from the command string,
        such as the full path to the application's script (from :const:`~.config.const.EXPATH`)
        or Python interpreter paths, to present a cleaner command representation
        (e.g., just "backup" instead of "/usr/bin/python3 /opt/bsm/cli.py backup ...").

        Args:
            command_string (str): The raw command string from a cron job.

        Returns:
            str: A potentially shortened version of the command, or the original
            string if formatting fails or doesn't apply.
        """
        try:
            command = command_string.strip()
            # Use str(EXPATH) to handle potential PathLike objects if EXPATH changes type.
            script_path_str = str(EXPATH)

            # Strip the full path to the script for brevity.
            if script_path_str and command.startswith(script_path_str):
                command = command[len(script_path_str) :].strip()

            parts = command.split()
            # Strip python interpreter if present.
            if parts and (
                parts[0].endswith("python")
                or parts[0].endswith("python3")
                or (
                    parts[0].endswith(".exe") and "python" in parts[0].lower()
                )  # More specific for .exe
            ):
                command = " ".join(parts[1:])

            # Return just the first part of the remaining command (e.g., "backup").
            main_command_action = command.split(maxsplit=1)[0]
            return main_command_action if main_command_action else command_string
        except Exception as e:
            logger.warning(
                f"Failed to format cron command '{command_string}' for display: {e}. Returning original.",
                exc_info=True,
            )
            return command_string

    def get_server_cron_jobs(self, server_name: str) -> List[str]:
        """Retrieves raw cron job lines for a specific server from the user's crontab.

        This method executes ``crontab -l`` to list all cron jobs for the current
        user. It then filters these jobs to find lines containing the argument
        ``--server "<server_name>"`` or ``--server <server_name>``, effectively
        isolating tasks related to the specified Bedrock server.
        Comments and empty lines in the crontab are ignored.

        Args:
            server_name (str): The name of the Bedrock server instance. Cron jobs
                containing ``--server "server_name"`` in their command will be matched.

        Returns:
            List[str]: A list of raw string representations of the cron jobs
            associated with the given `server_name`. Returns an empty list if no
            crontab exists for the user or if no matching jobs are found.

        Raises:
            InvalidServerNameError: If `server_name` is empty or not a string.
            SystemError: If executing ``crontab -l`` fails for reasons other
                than "no crontab for user" (e.g., `crontab` command issues,
                permission problems).
        """
        if not isinstance(server_name, str) or not server_name:
            raise InvalidServerNameError(
                "Server name cannot be empty and must be a string."
            )

        logger.debug(f"Retrieving cron jobs related to server '{server_name}'...")
        try:
            process = subprocess.run(
                [self.crontab_cmd, "-l"],
                capture_output=True,
                text=True,
                check=False,  # Do not raise exception for non-zero exit codes
                encoding="utf-8",
                errors="replace",  # Handle potential encoding issues in crontab output
            )

            # `crontab -l` returns 1 if no crontab exists, which is not an error here.
            if process.returncode == 0:
                all_jobs = process.stdout
            elif (
                process.returncode == 1
                and "no crontab for" in (process.stderr or "").lower()
            ):
                logger.info("No crontab found for the current user.")
                return []
            elif process.returncode != 0:  # Other errors
                raise SystemError(
                    f"Error running 'crontab -l'. Return code: {process.returncode}. Stderr: {process.stderr.strip() if process.stderr else 'N/A'}"
                )
            else:  # Should not happen if check=False and returncode is 0 or 1 with "no crontab"
                all_jobs = (
                    process.stdout
                )  # Assume success if no error and not the specific "no crontab" case

            # Filter lines to find those containing the specific server argument.
            # Ensure robust matching, e.g. considering quotes around server_name
            server_arg_pattern_v1 = f'--server "{server_name}"'  # With quotes
            server_arg_pattern_v2 = (
                f"--server {server_name}"  # Without quotes (less likely but possible)
            )

            filtered_jobs = []
            for line in all_jobs.splitlines():
                stripped_line = line.strip()
                if stripped_line and not stripped_line.startswith("#"):
                    # Check both patterns
                    if (
                        server_arg_pattern_v1 in stripped_line
                        or server_arg_pattern_v2 in stripped_line
                    ):
                        filtered_jobs.append(stripped_line)
            return filtered_jobs
        except Exception as e:
            # Catching broader Exception for robustness, then re-raising as SystemError
            raise SystemError(
                f"Unexpected error getting cron jobs for '{server_name}': {e}"
            ) from e

    def get_cron_jobs_table(self, cron_jobs: List[str]) -> List[Dict[str, str]]:
        """Formats a list of raw cron job strings into structured dictionaries for display.

        Each raw cron job string is parsed into its time components and command.
        The command is then formatted for easier display, and the schedule is
        converted into a more human-readable format.

        Args:
            cron_jobs (List[str]): A list of raw cron job strings, typically
                obtained from :meth:`.get_server_cron_jobs`.

        Returns:
            List[Dict[str, str]]: A list of dictionaries. Each dictionary represents
            a cron job and contains keys like "minute", "hour", "day_of_month",
            "month", "day_of_week", "command" (raw), "command_display" (formatted),
            and "schedule_time" (human-readable). Returns an empty list if
            `cron_jobs` is empty.
        """
        table_data: List[Dict[str, str]] = []
        if not cron_jobs:
            return table_data

        for line in cron_jobs:
            parsed_job = self._parse_cron_line(line)
            if not parsed_job:
                continue  # Skip lines that couldn't be parsed

            minute, hour, dom, month, dow, raw_command = parsed_job
            try:
                readable_schedule = self.convert_to_readable_schedule(
                    minute, hour, dom, month, dow
                )
            except UserInputError as e:
                # If conversion fails, use the raw cron time string as fallback
                readable_schedule = f"{minute} {hour} {dom} {month} {dow}"
                logger.warning(
                    f"Could not convert schedule '{readable_schedule}' to readable format for display: {e}."
                )

            display_command = self._format_cron_command(raw_command)

            table_data.append(
                {
                    "minute": minute,
                    "hour": hour,
                    "day_of_month": dom,
                    "month": month,
                    "day_of_week": dow,
                    "command": raw_command,
                    "command_display": display_command,
                    "schedule_time": readable_schedule,
                }
            )
        return table_data

    @staticmethod
    def _validate_cron_input(value: str, min_val: int, max_val: int) -> None:
        """Validates a single cron time field value if it's a simple number.

        This is a basic validation and does not attempt to parse complex cron
        expressions like "*/5" or "1-10". It only checks if `value` is a plain
        integer within the specified `min_val` and `max_val`. If `value` is "*",
        it's considered valid. Other non-integer strings are logged and skipped.

        Args:
            value (str): The cron field value (e.g., "5", "*", "*/15").
            min_val (int): The minimum allowed integer value for this field.
            max_val (int): The maximum allowed integer value for this field.

        Raises:
            UserInputError: If `value` is a simple integer outside the allowed range.
        """
        if value == "*":
            return
        try:
            # Only validate simple numeric values, not complex cron expressions.
            num = int(value)
            if not (min_val <= num <= max_val):
                raise UserInputError(
                    f"Value '{value}' is out of range ({min_val}-{max_val})."
                )
        except ValueError:
            # This occurs if `value` is not a simple integer (e.g., "*/5", "1,2,3")
            # These are valid cron expressions but not validated by this simple check.
            logger.debug(
                f"Cron value '{value}' is complex or non-numeric; skipping simple range validation."
            )
            pass  # Allow complex expressions to pass through this basic validation

    def convert_to_readable_schedule(
        self, minute: str, hour: str, day_of_month: str, month: str, day_of_week: str
    ) -> str:
        """Converts individual cron time fields into a human-readable schedule description.

        This method attempts to generate a user-friendly string representation
        of a cron schedule based on its five standard time components. It handles
        common patterns like daily, weekly, monthly, and yearly schedules.
        For more complex or unrecognized cron patterns, it returns a string
        showing the raw cron time fields.

        It uses internal helpers :meth:`._validate_cron_input`,
        :meth:`._get_cron_dow_name`, and :meth:`._get_cron_month_name` for
        validation and name conversion.

        Args:
            minute (str): The minute field (``0-59``, ``*``).
            hour (str): The hour field (``0-23, ``*``).
            day_of_month (str): The day of the month field (``1-31``, ``*``).
            month (str): The month field (``1-12``, ``*``, Jan-Dec).
            day_of_week (str): The day of the week field (``0-7``, ``*``, ``Sun-Sat``,
                where ``0`` and ``7`` are Sunday).

        Returns:
            str: A human-readable description of the schedule (e.g.,
            "Daily at 02:30", "Weekly on Sunday at 05:00") or the raw
            cron schedule string if it's a complex pattern.

        Raises:
            UserInputError: If any of the input time values are invalid or
                cannot be parsed by helper methods (e.g., invalid month name).
        """
        self._validate_cron_input(minute, 0, 59)
        self._validate_cron_input(hour, 0, 23)
        self._validate_cron_input(day_of_month, 1, 31)
        self._validate_cron_input(month, 1, 12)
        self._validate_cron_input(day_of_week, 0, 7)
        raw_schedule = f"{minute} {hour} {day_of_month} {month} {day_of_week}"
        try:
            # Attempt to convert common cron patterns into friendly text.
            if (
                minute == "*"
                and hour == "*"
                and day_of_month == "*"
                and month == "*"
                and day_of_week == "*"
            ):
                return "Every minute"
            if (
                minute != "*"
                and hour != "*"
                and day_of_month == "*"
                and month == "*"
                and day_of_week == "*"
            ):
                return f"Daily at {int(hour):02d}:{int(minute):02d}"
            if (
                minute != "*"
                and hour != "*"
                and day_of_month == "*"
                and month == "*"
                and day_of_week != "*"
            ):
                day_name = self._get_cron_dow_name(day_of_week)
                return f"Weekly on {day_name} at {int(hour):02d}:{int(minute):02d}"
            if (
                minute != "*"
                and hour != "*"
                and day_of_month != "*"
                and month == "*"
                and day_of_week == "*"
            ):
                return f"Monthly on day {int(day_of_month)} at {int(hour):02d}:{int(minute):02d}"
            if (
                minute != "*"
                and hour != "*"
                and day_of_month != "*"
                and month != "*"
                and day_of_week == "*"
            ):
                month_name = self._get_cron_month_name(month)
                return f"Yearly on {month_name} {int(day_of_month)} at {int(hour):02d}:{int(minute):02d}"
            return f"Cron schedule: {raw_schedule}"
        except (ValueError, UserInputError) as e:
            raise UserInputError(f"Invalid value in schedule: {raw_schedule}") from e

    def add_job(self, cron_string: str) -> None:
        """Adds a new cron job string to the current user's crontab.

        The method first retrieves the existing crontab content. If the exact
        `cron_string` already exists, it logs a warning and does nothing.
        Otherwise, it appends the new `cron_string` (followed by a newline)
        to the existing content (or creates a new crontab if none existed)
        and writes it back using ``crontab -``.

        Args:
            cron_string (str): The full cron job line to add (e.g.,
                ``"0 2 * * * /path/to/command --arg"``).

        Raises:
            MissingArgumentError: If `cron_string` is empty or contains only whitespace.
            SystemError: If reading the current crontab or writing the updated
                crontab fails due to ``crontab`` command errors or other
                unexpected issues.
        """
        if not cron_string or not cron_string.strip():
            raise MissingArgumentError("Cron job string cannot be empty.")
        cron_string = cron_string.strip()

        logger.info(f"Adding cron job: '{cron_string}'")
        try:
            # Get the current crontab content.
            process = subprocess.run(
                [self.crontab_cmd, "-l"],
                capture_output=True,
                text=True,
                check=False,  # Don't raise for "no crontab"
                encoding="utf-8",
                errors="replace",
            )
            current_crontab = ""
            if process.returncode == 0:
                current_crontab = process.stdout
            elif "no crontab for" not in (process.stderr or "").lower():
                # Raise error if 'crontab -l' failed for other reasons
                raise SystemError(
                    f"Error reading current crontab: {process.stderr.strip() if process.stderr else 'Unknown error'}"
                )

            # Check if the job already exists to avoid duplicates.
            if cron_string in [line.strip() for line in current_crontab.splitlines()]:
                logger.warning(
                    f"Cron job '{cron_string}' already exists. Skipping addition."
                )
                return

            # Append the new job and write the content back.
            # Ensure there's a newline if appending to existing content.
            new_crontab_content = current_crontab
            if new_crontab_content and not new_crontab_content.endswith("\n"):
                new_crontab_content += "\n"
            new_crontab_content += cron_string + "\n"

            write_process = subprocess.Popen(
                [self.crontab_cmd, "-"],  # Write to stdin of 'crontab -'
                stdin=subprocess.PIPE,
                text=True,  # Expect text input
                encoding="utf-8",
                errors="replace",
            )
            _, stderr = write_process.communicate(input=new_crontab_content)
            if write_process.returncode != 0:
                raise SystemError(
                    f"Failed to write updated crontab. Stderr: {stderr.strip() if stderr else 'Unknown error'}"
                )

            logger.info(f"Successfully added cron job: '{cron_string}'")
        except Exception as e:
            # Catching broader Exception for robustness, then re-raising as SystemError
            raise SystemError(
                f"Unexpected error adding cron job '{cron_string}': {e}"
            ) from e

    def update_job(self, old_cron_string: str, new_cron_string: str) -> None:
        """Replaces an existing cron job line with a new one in the user's crontab.

        It reads the current crontab, finds lines matching `old_cron_string`
        (exact match after stripping whitespace), and replaces them with
        `new_cron_string`. If `old_cron_string` is not found, a
        :class:`~.error.UserInputError` is raised.

        Args:
            old_cron_string (str): The exact cron job line to be replaced.
            new_cron_string (str): The new cron job line to substitute.

        Raises:
            MissingArgumentError: If either `old_cron_string` or `new_cron_string`
                is empty or contains only whitespace.
            UserInputError: If `old_cron_string` is not found in the current crontab.
            SystemError: If reading or writing the crontab fails.
        """
        if not old_cron_string or not old_cron_string.strip():
            raise MissingArgumentError("Old cron string cannot be empty.")
        if not new_cron_string or not new_cron_string.strip():
            raise MissingArgumentError("New cron string cannot be empty.")
        old_cron_string = old_cron_string.strip()
        new_cron_string = new_cron_string.strip()

        if old_cron_string == new_cron_string:
            logger.info(
                "Old and new cron strings are identical. No modification needed."
            )
            return

        logger.info(
            f"Attempting to modify cron job: Replace '{old_cron_string}' with '{new_cron_string}'"
        )
        try:
            process = subprocess.run(
                [self.crontab_cmd, "-l"],
                capture_output=True,
                text=True,
                check=False,
                encoding="utf-8",
                errors="replace",
            )
            current_crontab = ""
            if process.returncode == 0:
                current_crontab = process.stdout
            elif "no crontab for" not in (process.stderr or "").lower():
                raise SystemError(
                    f"Error reading current crontab: {process.stderr.strip() if process.stderr else 'Unknown error'}"
                )

            lines = current_crontab.splitlines()
            job_found = False
            updated_lines = []
            for line in lines:
                if line.strip() == old_cron_string:
                    updated_lines.append(new_cron_string)
                    job_found = True
                else:
                    updated_lines.append(line)

            if not job_found:
                raise UserInputError(
                    f"Cron job to modify was not found: '{old_cron_string}'"
                )

            new_crontab_content = "\n".join(updated_lines) + "\n"
            write_process = subprocess.Popen(
                [self.crontab_cmd, "-"],
                stdin=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            _, stderr = write_process.communicate(input=new_crontab_content)
            if write_process.returncode != 0:
                raise SystemError(
                    f"Failed to write modified crontab. Stderr: {stderr.strip() if stderr else 'Unknown error'}"
                )

            logger.info("Successfully modified cron job.")
        except Exception as e:
            raise SystemError(f"Unexpected error modifying cron job: {e}") from e

    def delete_job(self, cron_string: str) -> None:
        """Deletes a specific job line from the current user's crontab.

        It reads the current crontab, removes all lines that exactly match
        the provided `cron_string` (after stripping whitespace), and writes
        the modified content back. If the `cron_string` is not found, a warning
        is logged, and no changes are made. If removing the job results in an
        empty crontab, ``crontab -r`` is used to remove the crontab file itself.

        Args:
            cron_string (str): The exact cron job line to delete.

        Raises:
            MissingArgumentError: If `cron_string` is empty or contains only whitespace.
            SystemError: If reading or writing the crontab fails.
        """
        if not cron_string or not cron_string.strip():
            raise MissingArgumentError("Cron job string to delete cannot be empty.")
        cron_string = cron_string.strip()

        logger.info(f"Attempting to delete cron job: '{cron_string}'")
        try:
            process = subprocess.run(
                [self.crontab_cmd, "-l"],
                capture_output=True,
                text=True,
                check=False,  # Don't raise for "no crontab"
                encoding="utf-8",
                errors="replace",
            )
            current_crontab = ""
            if process.returncode == 0:
                current_crontab = process.stdout
            elif "no crontab for" not in (process.stderr or "").lower():
                raise SystemError(
                    f"Error reading current crontab: {process.stderr.strip() if process.stderr else 'Unknown error'}"
                )

            lines = current_crontab.splitlines()
            # Rebuild the crontab content, excluding the line to be deleted.
            updated_lines = [line for line in lines if line.strip() != cron_string]

            if len(lines) == len(updated_lines):
                logger.warning(
                    f"Cron job to delete was not found: '{cron_string}'. No changes made."
                )
                return

            # If the updated list of jobs is empty, remove the crontab entirely.
            if not updated_lines:
                logger.info(
                    "Last cron job removed. Deleting crontab file with 'crontab -r'."
                )
                # Use check=False as 'crontab -r' might also fail if no crontab exists,
                # though we expect one if we reached here from a non-empty 'lines'.
                subprocess.run(
                    [self.crontab_cmd, "-r"], check=False, capture_output=True
                )
            else:
                # If jobs remain, write them back to the file.
                new_crontab_content = "\n".join(updated_lines) + "\n"
                write_process = subprocess.Popen(
                    [self.crontab_cmd, "-"],
                    stdin=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                _, stderr = write_process.communicate(input=new_crontab_content)
                if write_process.returncode != 0:
                    raise SystemError(
                        f"Failed to write updated crontab after deletion. Stderr: {stderr.strip() if stderr else 'Unknown error'}"
                    )

            logger.info(f"Successfully deleted cron job: '{cron_string}'")
        except Exception as e:
            raise SystemError(
                f"Unexpected error deleting cron job '{cron_string}': {e}"
            ) from e


class WindowsTaskScheduler:
    """Manages scheduled tasks for Bedrock servers on Windows systems using ``schtasks``.

    This class provides an interface to interact with the Windows Task Scheduler
    for automating Bedrock server operations. It primarily uses the ``schtasks.exe``
    command-line utility for querying, creating (from XML), and deleting tasks.

    Tasks are typically defined in XML format, which this class can help generate
    (via :meth:`.create_task_xml`) and then import.

    Attributes:
        schtasks_cmd (str): The absolute path to the `schtasks.exe` executable.
    """

    XML_NAMESPACE: str = "{http://schemas.microsoft.com/windows/2004/02/mit/task}"
    """The XML namespace URI used in Windows Task Scheduler XML definitions."""

    def __init__(self) -> None:
        """Initializes the WindowsTaskScheduler.

        This constructor checks for the presence of the ``schtasks.exe`` command-line
        utility using ``shutil.which()``. If not found, it raises a
        :class:`~.error.CommandNotFoundError`.

        Raises:
            CommandNotFoundError: If the `schtasks` command is not available in
                the system's PATH.
        """
        self.schtasks_cmd: str = shutil.which("schtasks")  # type: ignore
        if not self.schtasks_cmd:
            logger.error("'schtasks' command not found. Cannot manage scheduled tasks.")
            raise CommandNotFoundError("schtasks")
        logger.debug(
            f"WindowsTaskScheduler initialized successfully with schtasks: {self.schtasks_cmd}"
        )

    def get_task_info(self, task_names: List[str]) -> List[Dict[str, str]]:
        """Retrieves details for specified Windows scheduled tasks.

        For each task name in `task_names`, this method queries the Windows Task
        Scheduler using ``schtasks /Query /TN <task_name> /XML`` to get its XML
        definition. It then parses this XML to extract a simplified command
        (first part of Arguments) and a human-readable schedule string.

        Args:
            task_names (List[str]): A list of task names to query. Task names
                are typically in a path-like format (e.g., ``\\MyTasks\\MyServerBackup``).

        Returns:
            List[Dict[str, str]]: A list of dictionaries. Each dictionary represents
            a successfully queried task and contains:

                - "task_name" (str): The name of the task.
                - "command" (str): A simplified command string (e.g., "backup").
                - "schedule" (str): A human-readable description of the task's schedule.

            Returns an empty list if `task_names` is empty. Tasks not found or
            those that cause parsing errors are omitted from the results and logged.
        """
        if not isinstance(task_names, list):
            # Consider raising TypeError, but for now, let's be consistent with current behavior.
            logger.error("get_task_info: Input 'task_names' must be a list.")
            return []  # Or raise TypeError("Input 'task_names' must be a list.")
        if not task_names:
            return []

        logger.debug(f"Querying Windows Task Scheduler for tasks: {task_names}")
        task_info_list: List[Dict[str, str]] = []

        for task_name in task_names:
            if not task_name or not isinstance(task_name, str):
                logger.warning(f"Skipping invalid task name provided: {task_name}")
                continue
            try:
                # Query the task and request its definition in XML format.
                result = subprocess.run(
                    [self.schtasks_cmd, "/Query", "/TN", task_name, "/XML"],
                    capture_output=True,
                    text=True,  # Decodes output as text
                    check=True,  # Raises CalledProcessError for non-zero exit codes
                    encoding="utf-8",  # Explicitly set encoding
                    errors="replace",  # Handle potential encoding errors in output
                )
                xml_output = result.stdout.strip()
                # Remove byte order mark (BOM) if present, common in Windows XML output.
                if xml_output.startswith("\ufeff"):
                    xml_output = xml_output[1:]

                root = ET.fromstring(xml_output)

                # Parse the XML to extract relevant information.
                # Find <Arguments> within <Exec> under <Actions>
                arguments_element = root.find(
                    f".//{self.XML_NAMESPACE}Actions/{self.XML_NAMESPACE}Exec/{self.XML_NAMESPACE}Arguments"
                )
                command_display = "N/A"
                if arguments_element is not None and arguments_element.text:
                    # Extract the first word of the arguments as the display command
                    arguments_text_val = arguments_element.text.strip()
                    if arguments_text_val:
                        command_display = arguments_text_val.split(maxsplit=1)[0]

                schedule_display = self._get_schedule_string(root)
                task_info_list.append(
                    {
                        "task_name": task_name,
                        "command": command_display,
                        "schedule": schedule_display,
                    }
                )

            except subprocess.CalledProcessError as e:
                stderr_lower = (e.stderr or "").strip().lower()
                # Handle the specific error for a task not being found more robustly.
                if (
                    "error: the system cannot find the file specified." in stderr_lower
                    or "error: the specified task name" in stderr_lower
                    and "does not exist" in stderr_lower
                    or "error: unable to find the specified task"
                    in stderr_lower  # Another possible message
                ):
                    logger.debug(f"Task '{task_name}' not found in Task Scheduler.")
                else:
                    logger.error(
                        f"Error running 'schtasks /Query' for task '{task_name}'. Stderr: {e.stderr.strip() if e.stderr else 'N/A'}",
                        exc_info=True,  # Include traceback for unexpected errors
                    )
            except ET.ParseError as e_parse:
                logger.error(
                    f"Error parsing XML output for task '{task_name}': {e_parse}. XML was: '{xml_output[:200]}...'",
                    exc_info=True,
                )
            except Exception as e_unexp:  # Catch-all for other unexpected issues
                logger.error(
                    f"Unexpected error processing task '{task_name}': {e_unexp}",
                    exc_info=True,
                )

        return task_info_list

    def _get_schedule_string(self, root: ET.Element) -> str:
        """Extracts and formats a human-readable schedule description from task XML.

        Parses various trigger types (TimeTrigger, CalendarTrigger for Daily,
        Weekly, Monthly schedules, LogonTrigger, BootTrigger) within the
        Task Scheduler XML structure and attempts to create a concise, readable
        summary of when the task is scheduled to run.

        Args:
            root (xml.etree.ElementTree.Element): The root XML element of a
                task definition (obtained from ``schtasks /Query /XML``).

        Returns:
            str: A comma-separated string of human-readable schedule descriptions
            (e.g., "Daily (every 1 days), On Logon"), or "No Triggers" if none
            are defined or parsed.
        """
        schedule_parts = []
        triggers_container = root.find(f".//{self.XML_NAMESPACE}Triggers")
        if triggers_container is None:
            return "No Triggers"

        for trigger in triggers_container:  # Iterate through child elements of Triggers
            trigger_tag = trigger.tag.replace(
                self.XML_NAMESPACE, ""
            )  # e.g., "TimeTrigger", "CalendarTrigger"
            part = f"Unknown Trigger Type ({trigger_tag})"  # Default

            start_boundary_el = trigger.find(f".//{self.XML_NAMESPACE}StartBoundary")
            start_time_str = "UnknownTime"
            if start_boundary_el is not None and start_boundary_el.text:
                try:
                    # Extract HH:MM:SS part from ISO 8601 datetime string
                    start_time_str = datetime.fromisoformat(
                        start_boundary_el.text.strip()
                    ).strftime("%H:%M:%S")
                except ValueError:
                    logger.debug(
                        f"Could not parse StartBoundary '{start_boundary_el.text}' as ISO datetime."
                    )
                    # Fallback for just time if T is present
                    if "T" in start_boundary_el.text:
                        start_time_str = start_boundary_el.text.split("T", 1)[-1]

            if trigger_tag == "TimeTrigger":
                part = f"One Time (at {start_time_str})"
            elif trigger_tag == "CalendarTrigger":
                # CalendarTrigger can be Daily, Weekly, or Monthly
                schedule_by_day = trigger.find(f".//{self.XML_NAMESPACE}ScheduleByDay")
                schedule_by_week = trigger.find(
                    f".//{self.XML_NAMESPACE}ScheduleByWeek"
                )
                schedule_by_month = trigger.find(
                    f".//{self.XML_NAMESPACE}ScheduleByMonth"
                )

                if schedule_by_day is not None:
                    interval_el = schedule_by_day.find(
                        f".//{self.XML_NAMESPACE}DaysInterval"
                    )
                    interval = (
                        interval_el.text
                        if interval_el is not None and interval_el.text
                        else "1"
                    )
                    part = f"Daily (every {interval} days at {start_time_str})"
                elif schedule_by_week is not None:
                    interval_el = schedule_by_week.find(
                        f".//{self.XML_NAMESPACE}WeeksInterval"
                    )
                    interval = (
                        interval_el.text
                        if interval_el is not None and interval_el.text
                        else "1"
                    )
                    days_of_week_el = schedule_by_week.find(
                        f".//{self.XML_NAMESPACE}DaysOfWeek"
                    )
                    days_list = []
                    if days_of_week_el is not None:
                        for day_el in days_of_week_el:  # Iterate direct children
                            days_list.append(day_el.tag.replace(self.XML_NAMESPACE, ""))
                    days_str = ", ".join(days_list) if days_list else "AnyDay"
                    part = f"Weekly (every {interval} weeks on {days_str} at {start_time_str})"
                elif schedule_by_month is not None:
                    # Simplified for brevity, can be expanded for specific days/months
                    part = f"Monthly (at {start_time_str})"
                else:
                    part = f"CalendarTrigger (complex, at {start_time_str})"

            elif trigger_tag == "LogonTrigger":
                part = "On Logon"
            elif trigger_tag == "BootTrigger":
                part = "On System Startup"
            # Add more trigger types as needed (e.g., EventTrigger, RegistrationTrigger)

            schedule_parts.append(part)

        return ", ".join(schedule_parts) if schedule_parts else "No Triggers"

    def get_server_task_names(
        self, server_name: str, config_dir: str
    ) -> List[Tuple[str, str]]:
        """Gets Windows Task Scheduler task names and their XML definition file paths
        associated with a specific Bedrock server.

        It scans the server's configuration subdirectory (``<config_dir>/<server_name>``)
        for ``.xml`` files. For each XML file found, it parses the file to extract
        the task's URI (which is its official name in Task Scheduler) from the
        ``<RegistrationInfo><URI>`` element.

        Args:
            server_name (str): The name of the server.
            config_dir (str): The main application configuration directory.
                The function looks for XML files in ``<config_dir>/<server_name>``.

        Returns:
            List[Tuple[str, str]]: A list of tuples. Each tuple contains:

                - ``task_name`` (str): The official task name (URI) from the XML.
                - ``xml_file_path`` (str): The absolute path to the XML definition file.

            Returns an empty list if the server's task directory doesn't exist
            or contains no valid task XML files.

        Raises:
            MissingArgumentError: If `server_name` or `config_dir` are empty.
            FileOperationError: If there's an ``OSError`` reading the task directory.
        """
        if not server_name:  # Basic check, more robust type checks can be added
            raise MissingArgumentError("Server name cannot be empty.")
        if not config_dir:
            raise MissingArgumentError("Config directory cannot be empty.")

        server_task_dir = os.path.join(config_dir, server_name)
        if not os.path.isdir(server_task_dir):
            logger.debug(f"Server task directory not found: {server_task_dir}")
            return []

        task_files: List[Tuple[str, str]] = []
        try:
            for filename in os.listdir(server_task_dir):
                if filename.lower().endswith(".xml"):
                    file_path = os.path.join(server_task_dir, filename)
                    try:
                        tree = ET.parse(file_path)
                        # Corrected XPath to find URI directly under RegistrationInfo
                        uri_element = tree.find(
                            f"./{self.XML_NAMESPACE}RegistrationInfo/{self.XML_NAMESPACE}URI"
                        )
                        if uri_element is not None and uri_element.text:
                            task_name = uri_element.text.strip().lstrip(
                                "\\"
                            )  # Remove leading backslash for consistency
                            if task_name:
                                task_files.append((task_name, file_path))
                            else:
                                logger.warning(
                                    f"Empty task URI found in XML file '{filename}'. Skipping."
                                )
                        else:
                            logger.warning(
                                f"No task URI found in XML file '{filename}'. Skipping."
                            )
                    except ET.ParseError as e_parse:
                        logger.error(
                            f"Error parsing task XML file '{filename}': {e_parse}. XML content might be malformed. Skipping.",
                            exc_info=True,
                        )
                    except (
                        Exception
                    ) as e_inner:  # Catch other unexpected errors during file processing
                        logger.error(
                            f"Unexpected error processing XML file '{filename}': {e_inner}. Skipping.",
                            exc_info=True,
                        )

        except OSError as e_os:
            raise FileOperationError(
                f"Error reading tasks from directory '{server_task_dir}': {e_os}"
            ) from e_os
        return task_files

    def create_task_xml(
        self,
        server_name: str,
        command: str,
        command_args: str,
        task_name: str,  # This is the desired Task Scheduler path, e.g., \MyTasks\MyBedrockTask
        config_dir: str,
        triggers: List[Dict[str, Any]],
        task_description: Optional[str] = None,
    ) -> str:
        """Creates an XML definition file for a Windows scheduled task.

        This method constructs an XML string conforming to the Windows Task Scheduler
        schema. The XML defines the task's registration information, triggers,
        principal (user context), settings, and actions (the command to execute).
        The generated XML is then saved to a file within the server's specific
        configuration subdirectory (``<config_dir>/<server_name>/<safe_task_name>.xml``).

        Args:
            server_name (str): The name of the Bedrock server this task is for.
                Used for logging and potentially in the task description.
            command (str): The primary command action this task will invoke via the
                main application script (e.g., "backup", "restart"). This becomes
                the first part of the ``<Arguments>`` in the XML.
            command_args (str): Additional arguments for the `command` (e.g.,
                ``--server "MyServer" --full``). These are appended to the `command`
                in ``<Arguments>``.
            task_name (str): The desired path and name for the task in Task Scheduler
                (e.g., ``\\MyApplicationTasks\\BackupMyServer``). This is stored in
                the ``<URI>`` element.
            config_dir (str): The main application configuration directory. The XML
                file will be saved in a subdirectory named after `server_name`.
            triggers (List[Dict[str, Any]]): A list of trigger dictionaries, each
                defining when the task should run. Each dictionary should specify
                a "type" (e.g., "TimeTrigger", "Daily", "Weekly", "Monthly") and
                other type-specific parameters (see :meth:`._add_trigger`).
            task_description (Optional[str], optional): A custom description for the
                task. If ``None``, a default description is generated.
                Defaults to ``None``.

        Returns:
            str: The absolute path to the generated XML file.

        Raises:
            MissingArgumentError: If any of `server_name`, `command`, `task_name`,
                or `config_dir` are empty.
            TypeError: If `triggers` is not a list.
            AppFileNotFoundError: If the main application script path (``EXPATH``)
                is not found (as it's used for the ``<Command>`` element).
            FileOperationError: If creating directories or writing the XML file fails.
            UserInputError: If trigger data is invalid (from :meth:`._add_trigger`).
        """
        if not all(
            [server_name, command, task_name, config_dir]
        ):  # Also check command_args?
            raise MissingArgumentError(
                "Required arguments (server_name, command, task_name, config_dir) cannot be empty."
            )
        if not isinstance(triggers, list):
            raise TypeError("Triggers must be a list of dictionaries.")
        if not EXPATH or not os.path.exists(EXPATH):  # EXPATH should be PathLike or str
            raise AppFileNotFoundError(
                str(EXPATH), "Main script executable for task command"
            )

        effective_description = (
            task_description
            or f"Scheduled task for Bedrock Server Manager: server '{server_name}', command '{command}'."
        )

        try:
            # Ensure the root element uses the namespace correctly without prefix for default
            task_attributes = {
                "version": "1.4",
                "xmlns": self.XML_NAMESPACE.strip(
                    "{}"
                ),  # Main namespace for the <Task> element
            }
            task = ET.Element("Task", attrib=task_attributes)

            reg_info = ET.SubElement(task, "RegistrationInfo")
            ET.SubElement(reg_info, "Date").text = datetime.now().isoformat(
                timespec="seconds"
            )
            ET.SubElement(reg_info, "Author").text = (
                f"{os.getenv('USERDOMAIN', '')}\\{os.getenv('USERNAME', 'SYSTEM')}"  # Fallback to SYSTEM
            )
            ET.SubElement(reg_info, "Description").text = effective_description
            # Ensure URI starts with a backslash as per schtasks convention
            ET.SubElement(reg_info, "URI").text = (
                task_name if task_name.startswith("\\") else f"\\{task_name}"
            )

            triggers_element = ET.SubElement(task, "Triggers")
            for trigger_data in triggers:
                self._add_trigger(
                    triggers_element, trigger_data
                )  # _add_trigger will use self.XML_NAMESPACE

            principals = ET.SubElement(task, "Principals")
            principal = ET.SubElement(
                principals, "Principal", id="Author"
            )  # id can be anything
            ET.SubElement(principal, "UserId").text = (
                os.getenv("USERNAME") or "SYSTEM"
            )  # Run as current user or SYSTEM
            ET.SubElement(principal, "LogonType").text = (
                "InteractiveToken"  # Or S4U for non-interactive
            )
            ET.SubElement(principal, "RunLevel").text = (
                "LeastPrivilege"  # Or HighestAvailable if admin needed by task
            )

            settings_el = ET.SubElement(task, "Settings")
            ET.SubElement(settings_el, "MultipleInstancesPolicy").text = "IgnoreNew"
            ET.SubElement(settings_el, "DisallowStartIfOnBatteries").text = "true"
            ET.SubElement(settings_el, "StopIfGoingOnBatteries").text = "true"
            ET.SubElement(settings_el, "AllowHardTerminate").text = "true"
            ET.SubElement(settings_el, "StartWhenAvailable").text = (
                "false"  # Or true if it should run if missed
            )
            ET.SubElement(settings_el, "ExecutionTimeLimit").text = (
                "PT0S"  # PT0S means indefinite
            )
            ET.SubElement(settings_el, "Priority").text = "7"  # 0-10, 7 is below normal
            ET.SubElement(settings_el, "Enabled").text = "true"

            actions = ET.SubElement(
                task, "Actions", Context="Author"
            )  # Context can be "Author" or "System"
            exec_action = ET.SubElement(actions, "Exec")
            ET.SubElement(exec_action, "Command").text = str(
                EXPATH
            )  # Path to this script/executable
            # Arguments are the command for this script (backup, restart) and its own args
            ET.SubElement(exec_action, "Arguments").text = (
                f"{command} {command_args}".strip()
            )
            # Optionally set WorkingDirectory if script relies on it
            # ET.SubElement(exec_action, "WorkingDirectory").text = os.path.dirname(str(EXPATH))

            server_config_dir = os.path.join(config_dir, server_name)
            os.makedirs(server_config_dir, exist_ok=True)
            # Sanitize task_name for use as a filename, replacing backslashes and other invalid chars
            safe_filename_base = task_name.replace("\\", "_").strip("_")
            safe_filename = re.sub(r'[/*?:"<>|]', "_", safe_filename_base) + ".xml"
            xml_file_path = os.path.join(server_config_dir, safe_filename)

            # Use ET.indent for pretty printing if Python 3.9+
            if hasattr(ET, "indent"):
                ET.indent(task)  # type: ignore

            tree = ET.ElementTree(task)
            # Task Scheduler XMLs are often UTF-16
            tree.write(xml_file_path, encoding="UTF-16", xml_declaration=True)
            logger.info(f"Task XML definition saved to: {xml_file_path}")
            return xml_file_path
        except Exception as e_xml:  # Catch broader errors during XML creation
            raise FileOperationError(
                f"Unexpected error creating task XML for '{task_name}': {e_xml}"
            ) from e_xml

    def import_task_from_xml(self, xml_file_path: str, task_name: str) -> None:
        """Imports a task definition from an XML file into Windows Task Scheduler.

        Uses ``schtasks /Create /TN <task_name> /XML <xml_file_path> /F`` to
        create or update (if ``/F`` is used) the task.

        Args:
            xml_file_path (str): The absolute path to the task definition XML file.
            task_name (str): The name/path of the task as it should appear in
                Task Scheduler (e.g., ``\\MyTasks\\MyBackupJob``). This should match
                the URI in the XML file.

        Raises:
            MissingArgumentError: If `xml_file_path` or `task_name` are empty.
            AppFileNotFoundError: If the `xml_file_path` does not exist.
            PermissionsError: If `schtasks` command fails due to access denied.
                This typically means the operation requires Administrator privileges.
            SystemError: For other ``schtasks`` command failures during import.
        """
        if not xml_file_path:
            raise MissingArgumentError("XML file path cannot be empty.")
        if not task_name:
            raise MissingArgumentError("Task name cannot be empty.")
        if not os.path.isfile(xml_file_path):
            raise AppFileNotFoundError(xml_file_path, "Task XML file")

        logger.info(f"Importing task '{task_name}' from XML file: {xml_file_path}")
        try:
            # Use /F to force an update if the task already exists.
            # Ensure task_name for /TN is correctly formatted (e.g., with leading backslash if needed by schtasks)
            tn_arg = task_name if task_name.startswith("\\") else f"\\{task_name}"
            subprocess.run(
                [
                    self.schtasks_cmd,
                    "/Create",
                    "/TN",
                    tn_arg,  # Use the task name from arg, should match URI in XML
                    "/XML",
                    xml_file_path,
                    "/F",  # Force update if exists
                ],
                check=True,  # Will raise CalledProcessError on failure
                capture_output=True,  # Capture stdout/stderr
                text=True,  # Decode as text
                encoding="utf-8",  # Specify encoding
                errors="replace",  # Handle potential decoding errors
            )
            logger.info(f"Task '{task_name}' imported/updated successfully.")
        except subprocess.CalledProcessError as e:
            stderr_msg = (e.stderr or "").strip()
            stdout_msg = (e.stdout or "").strip()
            # Check for common error messages
            if (
                "access is denied" in stderr_msg.lower()
                or "access is denied" in stdout_msg.lower()
            ):
                raise PermissionsError(
                    f"Access denied importing task '{task_name}'. This operation typically requires Administrator privileges. Stderr: {stderr_msg}"
                ) from e
            # Add more specific error checks if needed based on schtasks output
            raise SystemError(
                f"Failed to import task '{task_name}'. Schtasks exit code: {e.returncode}. Stderr: {stderr_msg}. Stdout: {stdout_msg}"
            ) from e

    def delete_task(self, task_name: str) -> None:
        """Deletes a scheduled task from Windows Task Scheduler using its name/path.

        Uses ``schtasks /Delete /TN <task_name> /F`` to remove the task.
        If the task does not exist, it logs this information and returns gracefully.

        Args:
            task_name (str): The name/path of the task to delete in Task Scheduler
                (e.g., ``\\MyTasks\\MyBackupJob``).

        Raises:
            MissingArgumentError: If `task_name` is empty.
            PermissionsError: If `schtasks` command fails due to access denied.
                This typically requires Administrator privileges.
            SystemError: For other ``schtasks`` command failures during deletion.
        """
        if not task_name:
            raise MissingArgumentError("Task name cannot be empty.")

        logger.info(f"Attempting to delete scheduled task: '{task_name}'")
        try:
            # Ensure task_name for /TN is correctly formatted
            tn_arg = task_name if task_name.startswith("\\") else f"\\{task_name}"
            subprocess.run(
                [
                    self.schtasks_cmd,
                    "/Delete",
                    "/TN",
                    tn_arg,
                    "/F",
                ],  # /F to force without prompt
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            logger.info(f"Task '{task_name}' deleted successfully.")
        except subprocess.CalledProcessError as e:
            stderr_msg = (e.stderr or "").strip().lower()
            stdout_msg = (
                (e.stdout or "").strip().lower()
            )  # Some messages might be on stdout

            # Check for "task not found" variations
            task_not_found_errors = [
                "the system cannot find the file specified",  # Generic file not found
                "the specified task name",
                "does not exist",  # Specific task not found message
                "unable to find the specified task",  # Another variation
            ]
            if any(err_text in stderr_msg for err_text in task_not_found_errors) or any(
                err_text in stdout_msg for err_text in task_not_found_errors
            ):
                logger.info(
                    f"Task '{task_name}' not found. Presumed already deleted or never existed."
                )
                return

            if "access is denied" in stderr_msg or "access is denied" in stdout_msg:
                raise PermissionsError(
                    f"Access denied deleting task '{task_name}'. This operation typically requires Administrator privileges. Stderr: {stderr_msg}"
                ) from e
            raise SystemError(
                f"Failed to delete task '{task_name}'. Schtasks exit code: {e.returncode}. Stderr: {stderr_msg}. Stdout: {stdout_msg}"
            ) from e

    def _get_day_element_name(self, day_input: Any) -> str:
        """Converts a day input (name, abbreviation, or number) to the
        corresponding Task Scheduler XML element name for ``<DaysOfWeek>``.

        Args:
            day_input (Any): The day input (e.g., "Mon", "Monday", 1, "7" for Sunday).

        Returns:
            str: The XML element name (e.g., "Monday", "Sunday").

        Raises:
            UserInputError: If `day_input` is not a recognized day.
        """
        day_str = str(day_input).strip().lower()
        # Mapping from various inputs to official Task Scheduler XML day names
        mapping = {
            "sun": "Sunday",
            "sunday": "Sunday",
            "0": "Sunday",
            "7": "Sunday",  # Cron 0/7 = Sunday
            "mon": "Monday",
            "monday": "Monday",
            "1": "Monday",
            "tue": "Tuesday",
            "tuesday": "Tuesday",
            "2": "Tuesday",
            "wed": "Wednesday",
            "wednesday": "Wednesday",
            "3": "Wednesday",
            "thu": "Thursday",
            "thursday": "Thursday",
            "4": "Thursday",
            "fri": "Friday",
            "friday": "Friday",
            "5": "Friday",
            "sat": "Saturday",
            "saturday": "Saturday",
            "6": "Saturday",
        }
        if day_str in mapping:
            return mapping[day_str]
        raise UserInputError(
            f"Invalid day of week: '{day_input}'. Use name, abbreviation (Sun-Sat), or number (0-6 or 1-7 where Sunday is 0 or 7)."
        )

    def _get_month_element_name(self, month_input: Any) -> str:
        """Converts a month input (name, abbreviation, or number) to the
        corresponding Task Scheduler XML element name for ``<Months>``.

        Args:
            month_input (Any): The month input (e.g., "Jan", "January", 1, "12").

        Returns:
            str: The XML element name (e.g., "January", "December").

        Raises:
            UserInputError: If `month_input` is not a recognized month.
        """
        month_str = str(month_input).strip().lower()
        mapping = {
            "jan": "January",
            "january": "January",
            "1": "January",
            "feb": "February",
            "february": "February",
            "2": "February",
            "mar": "March",
            "march": "March",
            "3": "March",
            "apr": "April",
            "april": "April",
            "4": "April",
            "may": "May",
            "may": "May",
            "5": "May",  # Corrected 'may' value
            "jun": "June",
            "june": "June",
            "6": "June",
            "jul": "July",
            "july": "July",
            "7": "July",
            "aug": "August",
            "august": "August",
            "8": "August",
            "sep": "September",
            "september": "September",
            "9": "September",
            "oct": "October",
            "october": "October",
            "10": "October",
            "nov": "November",
            "november": "November",
            "11": "November",
            "dec": "December",
            "december": "December",
            "12": "December",
        }
        # Allow full month names (already handled by lowercasing if mapping keys are lowercase)
        if month_str in mapping:
            return mapping[month_str]
        raise UserInputError(
            f"Invalid month: '{month_input}'. Use name, abbreviation (Jan-Dec), or number 1-12."
        )

    def _add_trigger(
        self, triggers_element: ET.Element, trigger_data: Dict[str, Any]
    ) -> None:
        """Adds a specific trigger sub-element to the main ``<Triggers>`` XML element.

        This is an internal helper for :meth:`.create_task_xml` to construct
        the XML for various trigger types based on a dictionary `trigger_data`.

        Supported `trigger_data["type"]` values:

            - "TimeTrigger": A one-time trigger. Requires `start` (ISO 8601 datetime).
            - "Daily": A daily calendar trigger. Requires `start`. Optional `interval` (days).
            - "Weekly": A weekly calendar trigger. Requires `start`, `days` (list of day names/numbers). Optional `interval` (weeks).
            - "Monthly": A monthly calendar trigger. Requires `start`, `days` (list of day numbers of month), `months` (list of month names/numbers).

        Args:
            triggers_element (xml.etree.ElementTree.Element): The parent ``<Triggers>`` XML element.
            trigger_data (Dict[str, Any]): A dictionary defining the trigger. Must
                contain a "type" key and other keys specific to that type.

        Raises:
            UserInputError: If `trigger_data` is missing required keys for its type,
                or if the trigger type is unsupported, or if day/month names are invalid.
        """
        trigger_type = trigger_data.get("type")
        start_boundary_iso = trigger_data.get("start")  # Expect YYYY-MM-DDTHH:MM:SS

        if not trigger_type:
            raise UserInputError("Trigger data must include a 'type' key.")
        if not start_boundary_iso and trigger_type in (
            "TimeTrigger",
            "Daily",
            "Weekly",
            "Monthly",
        ):
            raise UserInputError(
                f"Trigger type '{trigger_type}' requires a 'start' boundary in ISO format (YYYY-MM-DDTHH:MM:SS)."
            )

        # Common elements for many triggers
        common_trigger_elements = {
            f"{self.XML_NAMESPACE}Enabled": "true",
            # Add other common elements like EndBoundary, Repetition, etc. if needed
        }

        if trigger_type == "TimeTrigger":
            trigger = ET.SubElement(
                triggers_element, f"{self.XML_NAMESPACE}TimeTrigger"
            )
            ET.SubElement(trigger, f"{self.XML_NAMESPACE}StartBoundary").text = (
                start_boundary_iso
            )
            for tag, text in common_trigger_elements.items():
                ET.SubElement(trigger, tag).text = text

        elif trigger_type in ("Daily", "Weekly", "Monthly"):
            trigger = ET.SubElement(
                triggers_element, f"{self.XML_NAMESPACE}CalendarTrigger"
            )
            ET.SubElement(trigger, f"{self.XML_NAMESPACE}StartBoundary").text = (
                start_boundary_iso
            )
            for tag, text in common_trigger_elements.items():
                ET.SubElement(trigger, tag).text = text

            if trigger_type == "Daily":
                schedule = ET.SubElement(trigger, f"{self.XML_NAMESPACE}ScheduleByDay")
                ET.SubElement(schedule, f"{self.XML_NAMESPACE}DaysInterval").text = str(
                    trigger_data.get("interval", 1)
                )
            elif trigger_type == "Weekly":
                days_of_week_input = trigger_data.get("days")
                if not days_of_week_input or not isinstance(days_of_week_input, list):
                    raise UserInputError(
                        "Weekly trigger requires a list for 'days' (e.g., ['Monday', 'Fri'])."
                    )
                schedule = ET.SubElement(trigger, f"{self.XML_NAMESPACE}ScheduleByWeek")
                ET.SubElement(schedule, f"{self.XML_NAMESPACE}WeeksInterval").text = (
                    str(trigger_data.get("interval", 1))
                )
                days_of_week_el = ET.SubElement(
                    schedule, f"{self.XML_NAMESPACE}DaysOfWeek"
                )
                for day_input in days_of_week_input:
                    ET.SubElement(
                        days_of_week_el,
                        f"{self.XML_NAMESPACE}{self._get_day_element_name(day_input)}",
                    )
            elif trigger_type == "Monthly":
                days_of_month_input = trigger_data.get(
                    "days"
                )  # List of day numbers, e.g., [1, 15]
                months_input = trigger_data.get(
                    "months"
                )  # List of month names/numbers, e.g., ["Jan", 3]
                if not days_of_month_input or not isinstance(days_of_month_input, list):
                    raise UserInputError(
                        "Monthly trigger requires a list for 'days' (day numbers of month)."
                    )
                if not months_input or not isinstance(months_input, list):
                    raise UserInputError(
                        "Monthly trigger requires a list for 'months'."
                    )

                schedule = ET.SubElement(
                    trigger, f"{self.XML_NAMESPACE}ScheduleByMonth"
                )
                days_of_month_el = ET.SubElement(
                    schedule, f"{self.XML_NAMESPACE}DaysOfMonth"
                )
                for day_num in days_of_month_input:
                    ET.SubElement(days_of_month_el, f"{self.XML_NAMESPACE}Day").text = (
                        str(day_num)
                    )  # Day numbers
                months_el = ET.SubElement(schedule, f"{self.XML_NAMESPACE}Months")
                for month_val in months_input:
                    ET.SubElement(
                        months_el,
                        f"{self.XML_NAMESPACE}{self._get_month_element_name(month_val)}",
                    )
        # Add LogonTrigger, BootTrigger etc. as needed
        # elif trigger_type == "LogonTrigger":
        #     trigger = ET.SubElement(triggers_element, f"{self.XML_NAMESPACE}LogonTrigger")
        #     ET.SubElement(trigger, f"{self.XML_NAMESPACE}UserId").text = os.getenv('USERNAME') # Or specific user
        #     for tag, text in common_trigger_elements.items(): ET.SubElement(trigger, tag).text = text
        else:
            raise UserInputError(
                f"Unsupported trigger type for XML creation: '{trigger_type}'. Supported: TimeTrigger, Daily, Weekly, Monthly."
            )
        # ET.SubElement(trigger, f"{self.XML_NAMESPACE}Enabled").text = "true" # Moved to common_trigger_elements
