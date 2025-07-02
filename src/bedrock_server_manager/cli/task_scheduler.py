# bedrock_server_manager/cli/task_scheduler.py
"""
Defines the `bsm schedule` command group for managing OS-level scheduled tasks.

This module provides CLI tools to create, list, and delete scheduled tasks
that automate Bedrock server operations (e.g., backups, restarts, updates).
It offers a platform-aware interface, utilizing:

    -   Cron jobs on Linux systems.
    -   Windows Task Scheduler on Windows systems.

The main `bsm schedule` command, when invoked without subcommands, launches
an interactive menu-driven workflow for guided task management for a specified
server. Direct subcommands (`list`, `add`, `delete`) are also available for
more specific or scriptable operations.

Helper functions within this module handle user interaction for defining task
parameters (like cron schedules or Windows task triggers) and display formatted
lists of existing tasks. The actual scheduling operations are delegated to
functions in the :mod:`~bedrock_server_manager.api.task_scheduler` module.
"""

import logging
import platform
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import click
import questionary
from questionary import ValidationError, Validator

from bedrock_server_manager.api import task_scheduler as api_task_scheduler
from bedrock_server_manager.cli.utils import handle_api_response as _handle_api_response
from bedrock_server_manager.config.const import EXPATH
from bedrock_server_manager.error import BSMError

logger = logging.getLogger(__name__)


# --- Helper Functions and Validators ---


class CronTimeValidator(Validator):
    """
    A `questionary.Validator` that ensures cron time input fields are not empty.
    Used for interactive cron schedule input.
    """

    def validate(self, document):
        """
        Validates that the input text is not empty.

        Args:
            document: The `questionary` document object.

        Raises:
            ValidationError: If the input is empty.
        """
        if not document.text.strip():
            raise ValidationError(
                message="Input cannot be empty. Use '*' for any value.",
                cursor_position=0,
            )


class TimeValidator(Validator):
    """A `questionary.Validator` that validates time is in HH:MM format."""

    def validate(self, document):
        """
        Validates that the input text is a valid time in HH:MM format.

        Args:
            document: The `questionary` document object.

        Raises:
            ValidationError: If the input is not in HH:MM format.
        """
        try:
            time.strptime(document.text, "%H:%M")
        except ValueError:
            raise ValidationError(
                message="Please enter time in HH:MM format (e.g., 09:30 or 22:00).",
                cursor_position=len(document.text),
            )


def _get_windows_triggers_interactively() -> List[Dict[str, Any]]:
    """
    Interactively guides the user to define one or more triggers for a Windows Scheduled Task.

    Uses `questionary` to prompt for trigger types (Daily, Weekly) and their
    specific parameters (start time, days of the week).

    Returns:
        List[Dict[str, Any]]: A list of trigger dictionaries, where each dictionary
        conforms to the structure expected by the API for creating Windows tasks
        (typically including "type", "start", "start_time_display", and "days"
        for weekly triggers). Returns an empty list if the user chooses not to
        add any triggers or cancels the process.
    """
    triggers = []
    click.secho("\n--- Configure Task Triggers ---", bold=True)
    click.echo("A task can have multiple triggers (e.g., run daily and at startup).")

    while True:
        trigger_type = questionary.select(
            "Add a trigger type:", choices=["Daily", "Weekly", "Done Adding Triggers"]
        ).ask()
        if trigger_type is None or trigger_type == "Done Adding Triggers":
            break

        start_time_str = questionary.text(
            "Enter start time (HH:MM):", validate=TimeValidator()
        ).ask()
        if start_time_str is None:
            continue

        start_time_obj = datetime.strptime(start_time_str, "%H:%M").time()
        now = datetime.now()
        start_datetime = now.replace(
            hour=start_time_obj.hour,
            minute=start_time_obj.minute,
            second=0,
            microsecond=0,
        )

        if start_datetime < now:
            start_datetime += timedelta(days=1)
            click.secho(
                "Info: Time has passed for today; scheduling to start tomorrow.",
                fg="cyan",
            )

        start_boundary_iso = start_datetime.isoformat(timespec="seconds")

        if trigger_type == "Daily":
            triggers.append(
                {
                    "type": "Daily",
                    "start": start_boundary_iso,
                    "start_time_display": start_time_str,
                }
            )
            click.secho(
                f"Success: Added a 'Daily' trigger for {start_time_str}.", fg="green"
            )

        elif trigger_type == "Weekly":
            days = questionary.checkbox(
                "Select days of the week:",
                choices=[
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ],
            ).ask()
            if not days:
                click.secho(
                    "Warning: At least one day must be selected. Trigger not added.",
                    fg="yellow",
                )
                continue

            triggers.append(
                {
                    "type": "Weekly",
                    "start": start_boundary_iso,
                    "start_time_display": start_time_str,
                    "days": days,
                }
            )
            click.secho(
                f"Success: Added a 'Weekly' trigger for {start_time_str}.", fg="green"
            )
    return triggers


# --- Platform-Specific Display and Logic ---


def _display_cron_table(cron_jobs: List[str]):
    """
    Internal helper to display a list of cron jobs in a formatted table.

    Args:
        cron_jobs (List[str]): A list of raw cron job strings.
    """
    table_resp = api_task_scheduler.get_cron_jobs_table(cron_jobs)
    table_data = table_resp.get("table_data", [])

    if not table_data:
        click.secho("No scheduled cron jobs found for this application.", fg="cyan")
        return

    click.secho(f"\n{'SCHEDULE':<20} {'COMMAND':<30} {'HUMAN READABLE'}", bold=True)
    click.echo("-" * 80)
    for job in table_data:
        raw = f"{job['minute']} {job['hour']} {job['day_of_month']} {job['month']} {job['day_of_week']}"
        click.echo(
            f"{raw:<20} {job.get('command_display', 'N/A'):<30} {job.get('schedule_time', 'N/A')}"
        )
    click.echo("-" * 80)


def _display_windows_task_table(task_info_list: List[Dict]):
    """
    Internal helper to display a list of Windows scheduled tasks in a formatted table.

    Args:
        task_info_list (List[Dict[str, str]]): A list of dictionaries, where each
            dictionary contains details of a Windows task (e.g., "task_name",
            "command", "schedule").
    """
    if not task_info_list:
        click.secho("No scheduled tasks found for this server.", fg="cyan")
        return

    click.secho(f"\n{'TASK NAME':<40} {'COMMAND':<25} {'SCHEDULE'}", bold=True)
    click.echo("-" * 90)
    for task in task_info_list:
        click.echo(
            f"{task.get('task_name', 'N/A'):<40} {task.get('command', 'N/A'):<25} {task.get('schedule', 'N/A')}"
        )
    click.echo("-" * 90)


def _get_command_to_schedule(
    server_name: str, for_windows: bool
) -> Optional[Tuple[str, str]]:
    """
    Interactively prompts the user to select a predefined server command to schedule.

    Presents a list of common server actions (start, stop, restart, backup,
    update, prune backups).

    Args:
        server_name (str): The name of the server, used for constructing the
                           full cron command if `for_windows` is ``False``.
        for_windows (bool): If ``True``, returns the command slug. If ``False``
                            (for Linux cron), returns the fully constructed
                            command string including the application executable path.

    Returns:
        Optional[Tuple[str, str]]: A tuple containing:
            - User-friendly description of the command (e.g., "Start Server").
            - The command string or slug.
        Returns ``None`` if the user cancels the selection.
    """
    choices = {
        "Start Server": "server start",
        "Stop Server": "server stop",
        "Restart Server": "server restart",
        "Backup Server (World & Configs)": "backup create --type all",
        "Update Server": "server update",
        "Prune Backups": "backup prune",
    }
    selection = questionary.select(
        "Choose the command to schedule:",
        choices=sorted(list(choices.keys())) + ["Cancel"],
    ).ask()
    if not selection or selection == "Cancel":
        return None

    command_slug = choices[selection]
    if for_windows:
        return selection, command_slug
    else:
        full_command = f'{EXPATH} {command_slug} --server "{server_name}"'
        return selection, full_command


def _add_cron_job(server_name: str):
    """
    Interactive workflow to add a new cron job for a server on Linux.

    This helper function:

        1. Prompts the user to select a command to schedule using :func:`~._get_command_to_schedule`.
        2. Prompts for each cron time field (minute, hour, day of month, month, day of week)
           using `questionary.text` with :class:`~.CronTimeValidator`.
        3. Asks for confirmation before adding the constructed cron job string.
        4. Calls :func:`~bedrock_server_manager.api.task_scheduler.add_cron_job` to add the job.

    Args:
        server_name (str): The name of the server for which the cron job is being added.

    Raises:
        click.Abort: If the user cancels at any prompt.
    """
    _, command = _get_command_to_schedule(server_name, for_windows=False) or (
        None,
        None,
    )
    if not command:
        raise click.Abort()

    click.secho("\nEnter cron schedule details (* for any value):", bold=True)
    m = questionary.text(
        "Minute (0-59):", default="0", validate=CronTimeValidator()
    ).ask()
    h = questionary.text(
        "Hour (0-23):", default="*", validate=CronTimeValidator()
    ).ask()
    dom = questionary.text(
        "Day of Month (1-31):", default="*", validate=CronTimeValidator()
    ).ask()
    mon = questionary.text(
        "Month (1-12):", default="*", validate=CronTimeValidator()
    ).ask()
    dow = questionary.text(
        "Day of Week (0-6, 0=Sun):", default="*", validate=CronTimeValidator()
    ).ask()
    if any(
        p is None for p in [m, h, dom, mon, dow]
    ):  # Check if any prompt was cancelled
        raise click.Abort()

    new_cron_job = f"{m} {h} {dom} {mon} {dow} {command}"
    if questionary.confirm(
        f"\nAdd this cron job?\n  {new_cron_job}", default=True
    ).ask():
        resp = api_task_scheduler.add_cron_job(new_cron_job)
        _handle_api_response(resp, "Cron job added successfully.")
    else:  # User chose not to confirm
        raise click.Abort()


def _add_windows_task(server_name: str):
    """
    Interactive workflow to add a new Windows Scheduled Task for a server.

    This helper function:

        1. Prompts the user to select a command to schedule using :func:`~._get_command_to_schedule`.
        2. Guides the user to define triggers using :func:`~._get_windows_triggers_interactively`.
        3. If no triggers are defined, asks if a disabled task should be created.
        4. Generates a task name using :func:`~bedrock_server_manager.api.task_scheduler.create_task_name`.
        5. Displays a summary of the task to be created and asks for confirmation.
        6. Calls :func:`~bedrock_server_manager.api.task_scheduler.create_windows_task` to create the task.

    Args:
        server_name (str): The name of the server for which the task is being added.

    Raises:
        click.Abort: If the user cancels at any prompt.
    """
    desc, command_slug = _get_command_to_schedule(server_name, for_windows=True) or (
        None,
        None,
    )
    if not command_slug:
        raise click.Abort()

    triggers = _get_windows_triggers_interactively()
    if not triggers:
        if not questionary.confirm(
            "No triggers defined. Create a disabled task (for manual runs)?",
            default=False,
        ).ask():
            raise click.Abort()

    task_name = api_task_scheduler.create_task_name(
        server_name, desc if desc else "task"
    )  # Ensure desc is not None
    command_args = (
        f'--server "{server_name}"'  # Standard command args for server-specific tasks
    )

    click.secho(f"\nSummary of the task to be created:", bold=True)
    click.echo(f"  - {'Task Name':<12}: {task_name}")
    click.echo(f"  - {'Command':<12}: {command_slug} {command_args}")
    if triggers:
        click.echo("  - Triggers:")
        for t in triggers:
            display_time = t["start_time_display"]
            if t["type"] == "Daily":
                click.echo(f"    - Daily at {display_time}")
            else:
                click.echo(f"    - Weekly on {', '.join(t['days'])} at {display_time}")
    else:
        click.echo("  - Triggers:     None (task will be created disabled)")

    if questionary.confirm(f"\nCreate this scheduled task?", default=True).ask():
        resp = api_task_scheduler.create_windows_task(
            server_name, command_slug, command_args, task_name, triggers
        )
        _handle_api_response(resp, "Windows Scheduled Task created successfully.")


# --- Main Click Group and Commands ---


@click.group(invoke_without_command=True)
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="The target server for scheduling operations.",
)
@click.pass_context
def schedule(ctx: click.Context, server_name: str):
    """
    Manages scheduled tasks for a given server (OS-specific).

    This command group provides an interface to OS-level task schedulers
    (cron on Linux, Task Scheduler on Windows) for automating server actions
    like backups, updates, or restarts.

    If invoked without a subcommand (e.g., `bsm schedule -s MyServer`), it
    launches a full-screen interactive menu to guide the user through
    listing, adding, or deleting tasks for the specified server.

    Requires the `-s, --server SERVER_NAME` option to specify the target server.

    Subcommands:
        list: Lists existing scheduled tasks for the server.
        add: Interactively adds a new scheduled task for the server.
        delete: Interactively deletes an existing scheduled task for the server.
    """
    os_type = platform.system()
    if os_type not in ("Linux", "Windows"):
        click.secho(
            f"Error: Task scheduling is not supported on this OS ({os_type}).", fg="red"
        )
        return

    ctx.obj = {"server_name": server_name, "os_type": os_type}
    if ctx.invoked_subcommand is None:
        while True:
            try:
                click.clear()
                click.secho(
                    f"--- Task Management Menu for Server: {server_name} ---", bold=True
                )
                ctx.invoke(list_tasks)

                choice = questionary.select(
                    "\nSelect an action:",
                    choices=["Add New Task", "Delete Task", "Exit"],
                ).ask()

                if not choice or choice == "Exit":
                    break
                elif choice == "Add New Task":
                    ctx.invoke(add_task)
                elif choice == "Delete Task":
                    ctx.invoke(delete_task)

                questionary.press_any_key_to_continue(
                    "Press any key to return to the menu..."
                ).ask()
            except (click.Abort, KeyboardInterrupt):
                break
        click.secho("\nExiting scheduler menu.", fg="cyan")


@schedule.command("list")
@click.pass_context
def list_tasks(ctx: click.Context):
    """
    Lists all scheduled tasks associated with the specified server.

    The output format is platform-specific:

        -   On Linux, it displays cron jobs relevant to the server.
        -   On Windows, it displays tasks from the Windows Task Scheduler.

    This command is typically invoked via the main `schedule` group's context.
    """
    server_name, os_type = ctx.obj["server_name"], ctx.obj["os_type"]
    if os_type == "Linux":
        resp = api_task_scheduler.get_server_cron_jobs(server_name)
        _display_cron_table(resp.get("cron_jobs", []))
    elif os_type == "Windows":
        task_names_resp = api_task_scheduler.get_server_task_names(server_name)
        task_info_resp = api_task_scheduler.get_windows_task_info(
            [t[0] for t in task_names_resp.get("task_names", [])]
        )
        _display_windows_task_table(task_info_resp.get("task_info", []))


@schedule.command("add")
@click.pass_context
def add_task(ctx: click.Context):
    """
    Interactively adds a new scheduled task for the specified server.

    This command launches a platform-specific interactive workflow:

        -   :func:`~._add_cron_job` on Linux.
        -   :func:`~._add_windows_task` on Windows.

    These workflows guide the user through selecting a command to schedule
    and defining the schedule parameters (cron expression or task triggers).

    This command is typically invoked via the main `schedule` group's context.
    """
    server_name, os_type = ctx.obj["server_name"], ctx.obj["os_type"]
    try:
        if os_type == "Linux":
            _add_cron_job(server_name)
        elif os_type == "Windows":
            _add_windows_task(server_name)
    except (click.Abort, KeyboardInterrupt, BSMError) as e:
        # Catch BSMError here to provide a consistent cancel/error message
        if isinstance(e, BSMError):
            logger.error(f"Failed to add task: {e}", exc_info=True)
        click.secho("\nAdd operation cancelled.", fg="yellow")


@schedule.command("delete")
@click.pass_context
def delete_task(ctx: click.Context):
    """
    Interactively deletes an existing scheduled task for the specified server.

    This command first lists the available tasks (cron jobs on Linux,
    scheduled tasks on Windows) for the server and then prompts the user
    to select one for deletion. A confirmation is required before the
    deletion is performed.

    This command is typically invoked via the main `schedule` group's context.
    """
    server_name, os_type = ctx.obj["server_name"], ctx.obj["os_type"]
    try:
        if os_type == "Linux":
            jobs = api_task_scheduler.get_server_cron_jobs(server_name).get(
                "cron_jobs", []
            )
            if not jobs:
                click.secho("No scheduled jobs found to delete.", fg="yellow")
                return
            job_to_delete = questionary.select(
                "Select job to delete:", choices=jobs + ["Cancel"]
            ).ask()
            if job_to_delete and job_to_delete != "Cancel":
                if questionary.confirm(
                    f"Delete this job?\n  {job_to_delete}", default=False
                ).ask():
                    _handle_api_response(
                        api_task_scheduler.delete_cron_job(job_to_delete),
                        "Job deleted successfully.",
                    )

        elif os_type == "Windows":
            tasks = api_task_scheduler.get_server_task_names(server_name).get(
                "task_names", []
            )
            if not tasks:
                click.secho("No scheduled tasks found to delete.", fg="yellow")
                return
            task_map = {t[0]: t for t in tasks}
            task_name_to_delete = questionary.select(
                "Select task to delete:",
                choices=sorted(list(task_map.keys())) + ["Cancel"],
            ).ask()
            if task_name_to_delete and task_name_to_delete != "Cancel":
                if questionary.confirm(
                    f"Delete task '{task_name_to_delete}'?", default=False
                ).ask():
                    _, file_path = task_map[task_name_to_delete]
                    _handle_api_response(
                        api_task_scheduler.delete_windows_task(
                            task_name_to_delete, file_path
                        ),
                        "Task deleted successfully.",
                    )
    except (click.Abort, KeyboardInterrupt):
        click.secho("\nDelete operation cancelled.", fg="yellow")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    schedule()
