# bedrock_server_manager/cli/task_scheduler.py
"""
Defines the `bsm schedule` command group for managing scheduled tasks.

This module provides a platform-aware interface for creating, viewing,
and deleting scheduled tasks using cron (on Linux) or the Task Scheduler
(on Windows). It features a main interactive menu for guided management.
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
    """A `questionary.Validator` that ensures cron time input is not empty."""

    def validate(self, document):
        if not document.text.strip():
            raise ValidationError(
                message="Input cannot be empty. Use '*' for any value.",
                cursor_position=0,
            )


class TimeValidator(Validator):
    """A `questionary.Validator` that validates time is in HH:MM format."""

    def validate(self, document):
        try:
            time.strptime(document.text, "%H:%M")
        except ValueError:
            raise ValidationError(
                message="Please enter time in HH:MM format (e.g., 09:30 or 22:00).",
                cursor_position=len(document.text),
            )


def _get_windows_triggers_interactively() -> List[Dict[str, Any]]:
    """Guides the user to create triggers for a Windows Scheduled Task."""
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
    """Displays a formatted table of cron jobs."""
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
    """Displays a formatted table of Windows scheduled tasks."""
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
    """Prompts user to select a command to schedule."""
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
    """Interactive workflow to add a new cron job for Linux."""
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
    if any(p is None for p in [m, h, dom, mon, dow]):
        raise click.Abort()

    new_cron_job = f"{m} {h} {dom} {mon} {dow} {command}"
    if questionary.confirm(
        f"\nAdd this cron job?\n  {new_cron_job}", default=True
    ).ask():
        resp = api_task_scheduler.add_cron_job(new_cron_job)
        _handle_api_response(resp, "Cron job added successfully.")


def _add_windows_task(server_name: str):
    """Interactive workflow to add a new Windows Scheduled Task."""
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

    task_name = api_task_scheduler.create_task_name(server_name, desc)
    command_args = f'--server "{server_name}"'

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
    """Manages scheduled tasks for a server (cron/Windows Task Scheduler).

    When run without a subcommand, it launches a full-screen interactive menu
    for managing scheduled tasks for the specified server.
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
    """Lists all scheduled tasks associated with this application."""
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
    """Interactively adds a new platform-specific scheduled task."""
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
    """Interactively deletes an existing scheduled task."""
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
