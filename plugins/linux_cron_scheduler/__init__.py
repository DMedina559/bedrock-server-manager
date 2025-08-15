# <PLUGIN_DIR>/linux_cron_scheduler/__init__.py
import logging
import platform
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import subprocess
import shutil
import re

import click
import questionary
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from questionary import ValidationError, Validator

from bedrock_server_manager.plugin_base import PluginBase
from bedrock_server_manager.config import EXPATH
from bedrock_server_manager.error import (
    BSMError,
    CommandNotFoundError,
    SystemError,
    InvalidServerNameError,
    UserInputError,
    MissingArgumentError,
)
from bedrock_server_manager.web.dependencies import get_current_active_user
from bedrock_server_manager.web.schemas import User
from bedrock_server_manager.web.templating import templates

logger = logging.getLogger(__name__)


class LinuxCronSchedulerPlugin(PluginBase):
    version = "1.0.0"
    name = "linux_cron_scheduler"

    def on_load(self):
        self.logger.info("Linux Cron Scheduler Plugin Loaded")
        if platform.system() == "Linux":
            self.add_click_command(schedule)
            self.add_fastapi_router(router)
            self.add_template_folder("templates")
            self.add_static_folder("static")


class CronTimeValidator(Validator):
    def validate(self, document):
        if not document.text.strip():
            raise ValidationError(
                message="Input cannot be empty. Use '*' for any value.",
                cursor_position=0,
            )


def _get_command_to_schedule(server_name: str) -> Optional[Tuple[str, str]]:
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
    full_command = f'{EXPATH} {command_slug} --server "{server_name}"'
    return selection, full_command


def _add_cron_job(server_name: str):
    _, command = _get_command_to_schedule(server_name) or (None, None)
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
        try:
            scheduler = LinuxTaskScheduler()
            scheduler.add_job(new_cron_job)
            click.secho("Cron job added successfully.", fg="green")
        except BSMError as e:
            click.secho(f"Error adding cron job: {e}", fg="red")


def _display_cron_table(cron_jobs: List[str]):
    scheduler = LinuxTaskScheduler()
    table_data = scheduler.get_cron_jobs_table(cron_jobs)

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
    if platform.system() != "Linux":
        click.secho("This command is only available on Linux.", fg="red")
        return

    ctx.obj = {"server_name": server_name}
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
    server_name = ctx.obj["server_name"]
    try:
        scheduler = LinuxTaskScheduler()
        jobs = scheduler.get_server_cron_jobs(server_name)
        _display_cron_table(jobs)
    except BSMError as e:
        click.secho(f"Error listing cron jobs: {e}", fg="red")


@schedule.command("add")
@click.pass_context
def add_task(ctx: click.Context):
    server_name = ctx.obj["server_name"]
    try:
        _add_cron_job(server_name)
    except (click.Abort, KeyboardInterrupt, BSMError) as e:
        if isinstance(e, BSMError):
            logger.error(f"Failed to add task: {e}", exc_info=True)
        click.secho("\nAdd operation cancelled.", fg="yellow")


@schedule.command("delete")
@click.pass_context
def delete_task(ctx: click.Context):
    server_name = ctx.obj["server_name"]
    try:
        scheduler = LinuxTaskScheduler()
        jobs = scheduler.get_server_cron_jobs(server_name)
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
                scheduler.delete_job(job_to_delete)
                click.secho("Job deleted successfully.", fg="green")
    except (click.Abort, KeyboardInterrupt):
        click.secho("\nDelete operation cancelled.", fg="yellow")


class LinuxTaskScheduler:
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
        "7": "Sunday",
    }

    def __init__(self) -> None:
        self.crontab_cmd: str = shutil.which("crontab")
        if not self.crontab_cmd:
            raise CommandNotFoundError("crontab")

    def _get_cron_month_name(self, month_input: str) -> str:
        month_str = str(month_input).strip().lower()
        if month_str in self._CRON_MONTHS_MAP:
            return self._CRON_MONTHS_MAP[month_str]
        else:
            raise UserInputError(f"Invalid month value: '{month_input}'.")

    def _get_cron_dow_name(self, dow_input: str) -> str:
        dow_str = str(dow_input).strip().lower()
        if dow_str == "7":
            dow_str = "0"
        if dow_str in self._CRON_DAYS_MAP:
            return self._CRON_DAYS_MAP[dow_str]
        else:
            raise UserInputError(f"Invalid day-of-week value: '{dow_input}'.")

    @staticmethod
    def _parse_cron_line(line: str) -> Optional[Tuple[str, str, str, str, str, str]]:
        parts = line.strip().split(maxsplit=5)
        if len(parts) == 6:
            return tuple(parts)
        return None

    @staticmethod
    def _format_cron_command(command_string: str) -> str:
        try:
            command = command_string.strip()
            script_path_str = str(EXPATH)
            if script_path_str and command.startswith(script_path_str):
                command = command[len(script_path_str) :].strip()
            parts = command.split()
            if parts and (parts[0].endswith("python") or parts[0].endswith("python3")):
                command = " ".join(parts[1:])
            main_command_action = command.split(maxsplit=1)[0]
            return main_command_action if main_command_action else command_string
        except Exception:
            return command_string

    def get_server_cron_jobs(self, server_name: str) -> List[str]:
        if not isinstance(server_name, str) or not server_name:
            raise InvalidServerNameError("Server name must be a non-empty string.")
        try:
            process = subprocess.run(
                [self.crontab_cmd, "-l"], capture_output=True, text=True, check=False
            )
            if process.returncode == 0:
                all_jobs = process.stdout
            elif (
                process.returncode == 1
                and "no crontab for" in (process.stderr or "").lower()
            ):
                return []
            else:
                raise SystemError(
                    f"Error running 'crontab -l': {process.stderr.strip()}"
                )
            server_arg_pattern_v1 = f'--server "{server_name}"'
            server_arg_pattern_v2 = f"--server {server_name}"
            filtered_jobs = []
            for line in all_jobs.splitlines():
                stripped_line = line.strip()
                if stripped_line and not stripped_line.startswith("#"):
                    if (
                        server_arg_pattern_v1 in stripped_line
                        or server_arg_pattern_v2 in stripped_line
                    ):
                        filtered_jobs.append(stripped_line)
            return filtered_jobs
        except Exception as e:
            raise SystemError(f"Unexpected error getting cron jobs: {e}") from e

    def get_cron_jobs_table(self, cron_jobs: List[str]) -> List[Dict[str, str]]:
        table_data: List[Dict[str, str]] = []
        if not cron_jobs:
            return table_data
        for line in cron_jobs:
            parsed_job = self._parse_cron_line(line)
            if not parsed_job:
                continue
            minute, hour, dom, month, dow, raw_command = parsed_job
            try:
                readable_schedule = self.convert_to_readable_schedule(
                    minute, hour, dom, month, dow
                )
            except UserInputError:
                readable_schedule = f"{minute} {hour} {dom} {month} {dow}"
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
        if value == "*":
            return
        try:
            num = int(value)
            if not (min_val <= num <= max_val):
                raise UserInputError(
                    f"Value '{value}' is out of range ({min_val}-{max_val})."
                )
        except ValueError:
            pass

    def convert_to_readable_schedule(
        self, minute: str, hour: str, day_of_month: str, month: str, day_of_week: str
    ) -> str:
        self._validate_cron_input(minute, 0, 59)
        self._validate_cron_input(hour, 0, 23)
        self._validate_cron_input(day_of_month, 1, 31)
        self._validate_cron_input(month, 1, 12)
        self._validate_cron_input(day_of_week, 0, 7)
        raw_schedule = f"{minute} {hour} {day_of_month} {month} {day_of_week}"
        try:
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
        if not cron_string or not cron_string.strip():
            raise MissingArgumentError("Cron job string cannot be empty.")
        cron_string = cron_string.strip()
        try:
            process = subprocess.run(
                [self.crontab_cmd, "-l"], capture_output=True, text=True, check=False
            )
            current_crontab = ""
            if process.returncode == 0:
                current_crontab = process.stdout
            elif "no crontab for" not in (process.stderr or "").lower():
                raise SystemError(
                    f"Error reading current crontab: {process.stderr.strip()}"
                )
            if cron_string in [line.strip() for line in current_crontab.splitlines()]:
                return
            new_crontab_content = current_crontab
            if new_crontab_content and not new_crontab_content.endswith("\n"):
                new_crontab_content += "\n"
            new_crontab_content += cron_string + "\n"
            write_process = subprocess.Popen(
                [self.crontab_cmd, "-"], stdin=subprocess.PIPE, text=True
            )
            _, stderr = write_process.communicate(input=new_crontab_content)
            if write_process.returncode != 0:
                raise SystemError(
                    f"Failed to write updated crontab. Stderr: {stderr.strip()}"
                )
        except Exception as e:
            raise SystemError(f"Unexpected error adding cron job: {e}") from e

    def delete_job(self, cron_string: str) -> None:
        if not cron_string or not cron_string.strip():
            raise MissingArgumentError("Cron job string to delete cannot be empty.")
        cron_string = cron_string.strip()
        try:
            process = subprocess.run(
                [self.crontab_cmd, "-l"], capture_output=True, text=True, check=False
            )
            current_crontab = ""
            if process.returncode == 0:
                current_crontab = process.stdout
            elif "no crontab for" not in (process.stderr or "").lower():
                raise SystemError(
                    f"Error reading current crontab: {process.stderr.strip()}"
                )
            lines = current_crontab.splitlines()
            updated_lines = [line for line in lines if line.strip() != cron_string]
            if len(lines) == len(updated_lines):
                return
            if not updated_lines:
                subprocess.run(
                    [self.crontab_cmd, "-r"], check=False, capture_output=True
                )
            else:
                new_crontab_content = "\n".join(updated_lines) + "\n"
                write_process = subprocess.Popen(
                    [self.crontab_cmd, "-"], stdin=subprocess.PIPE, text=True
                )
                _, stderr = write_process.communicate(input=new_crontab_content)
                if write_process.returncode != 0:
                    raise SystemError(
                        f"Failed to write updated crontab after deletion. Stderr: {stderr.strip()}"
                    )
        except Exception as e:
            raise SystemError(f"Unexpected error deleting cron job: {e}") from e


router = APIRouter(
    prefix="/linux_cron_scheduler",
    tags=["Linux Cron Scheduler"],
)


@router.get("/schedule-tasks/{server_name}", response_class=HTMLResponse)
async def schedule_tasks_linux_page_route(
    request: Request,
    server_name: str,
    current_user: User = Depends(get_current_active_user),
):
    scheduler = LinuxTaskScheduler()
    cron_jobs = scheduler.get_server_cron_jobs(server_name)
    table_data = scheduler.get_cron_jobs_table(cron_jobs)
    return templates.TemplateResponse(
        "schedule_tasks.html",
        {
            "request": request,
            "current_user": current_user,
            "server_name": server_name,
            "table_data": table_data,
            "EXPATH": EXPATH,
            "error_message": None,
        },
    )


@router.get("/jobs/{server_name}", dependencies=[Depends(get_current_active_user)])
def get_server_cron_jobs_api(server_name: str):
    scheduler = LinuxTaskScheduler()
    return scheduler.get_server_cron_jobs(server_name)


@router.post("/jobs", dependencies=[Depends(get_current_active_user)])
def add_cron_job_api(cron_job: Dict[str, str]):
    scheduler = LinuxTaskScheduler()
    scheduler.add_job(cron_job["cron_job_string"])
    return {"status": "success"}


@router.delete("/jobs", dependencies=[Depends(get_current_active_user)])
def delete_cron_job_api(cron_job: Dict[str, str]):
    scheduler = LinuxTaskScheduler()
    scheduler.delete_job(cron_job["cron_job_string"])
    return {"status": "success"}
