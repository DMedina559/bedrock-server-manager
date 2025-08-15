# <PLUGIN_DIR>/windows_task_scheduler/__init__.py
import logging
import platform
from pathlib import Path
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import subprocess
import shutil
import re
import os
import xml.etree.ElementTree as ET

import click
import questionary
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from questionary import ValidationError, Validator

from bedrock_server_manager import PluginBase
from bedrock_server_manager.cli.utils import get_server_name_interactively
from bedrock_server_manager.config import EXPATH
from bedrock_server_manager.error import (
    BSMError,
    CommandNotFoundError,
    SystemError,
    InvalidServerNameError,
    UserInputError,
    MissingArgumentError,
    FileOperationError,
    AppFileNotFoundError,
    PermissionsError,
)
from bedrock_server_manager.instances import get_settings_instance
from bedrock_server_manager.utils import get_timestamp
from bedrock_server_manager.web import get_current_user
from bedrock_server_manager.web.templating import templates

logger = logging.getLogger(__name__)


class WindowsTaskSchedulerPlugin(PluginBase):
    version = "1.0.0"

    def on_load(self):
        self.logger.info("Windows Task Scheduler Plugin Loaded")

    def get_cli_commands(self):
        return [schedule]

    def get_fastapi_routers(self):
        return [router]

    def get_template_paths(self) -> list[Path]:
        """Returns the path to this plugin's templates directory."""
        plugin_root_dir = Path(__file__).parent
        template_dir = plugin_root_dir / "templates"
        # It's good practice to ensure the directory actually exists before returning it
        if not template_dir.is_dir():
            self.logger.warning(
                f"Template directory not found for {self.name} at {template_dir}. Page might not load."
            )
            return []
        return [template_dir]

    def get_static_mounts(self) -> list[Path]:
        """Returns the path to this plugin's static directory."""
        plugin_root_dir = Path(__file__).parent
        static_dir = plugin_root_dir / "static"
        # It's good practice to ensure the directory actually exists before returning it
        if not static_dir.is_dir():
            self.logger.warning(
                f"Static directory not found for {self.name} at {static_dir}. Page might not load."
            )
            return []
        return [static_dir]

    def get_cli_menu_items(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "Task Scheduler",
                "handler": task_scheduler_menu,
            }
        ]


class TimeValidator(Validator):
    def validate(self, document):
        try:
            time.strptime(document.text, "%H:%M")
        except ValueError:
            raise ValidationError(
                message="Please enter time in HH:MM format (e.g., 09:30 or 22:00).",
                cursor_position=len(document.text),
            )


def _get_windows_triggers_interactively() -> List[Dict[str, Any]]:
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


def _display_windows_task_table(task_info_list: List[Dict]):
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
    return selection, command_slug


def _add_windows_task(server_name: str):
    desc, command_slug = _get_command_to_schedule(server_name) or (None, None)
    if not command_slug:
        raise click.Abort()

    triggers = _get_windows_triggers_interactively()
    if not triggers:
        if not questionary.confirm(
            "No triggers defined. Create a disabled task (for manual runs)?",
            default=False,
        ).ask():
            raise click.Abort()

    task_name = create_task_name(server_name, desc if desc else "task")
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
        try:
            scheduler = WindowsTaskScheduler()
            scheduler.create_task_xml(
                server_name,
                command_slug,
                command_args,
                task_name,
                get_settings_instance().config_dir,
                triggers,
            )
            scheduler.import_task_from_xml(
                os.path.join(
                    get_settings_instance().config_dir,
                    server_name,
                    re.sub(r'[\\/*?:"<>|]', "_", task_name) + ".xml",
                ),
                task_name,
            )
            click.secho("Windows Scheduled Task created successfully.", fg="green")
        except BSMError as e:
            click.secho(f"Error creating Windows Scheduled Task: {e}", fg="red")


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
    if platform.system() != "Windows":
        click.secho("This command is only available on Windows.", fg="red")
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


def task_scheduler_menu(ctx: click.Context):
    """Main menu for Windows Task Scheduler operations."""
    if platform.system() != "Windows":
        click.secho("This command is only available on Windows.", fg="red")
        return
    server_name = get_server_name_interactively()
    ctx.invoke(schedule, server_name=server_name)


@schedule.command("list")
@click.pass_context
def list_tasks(ctx: click.Context):
    server_name = ctx.obj["server_name"]
    try:
        scheduler = WindowsTaskScheduler()
        task_names = scheduler.get_server_task_names(
            server_name, get_settings_instance().config_dir
        )
        task_info = scheduler.get_task_info([t[0] for t in task_names])
        _display_windows_task_table(task_info)
    except BSMError as e:
        click.secho(f"Error listing Windows Scheduled Tasks: {e}", fg="red")


@schedule.command("add")
@click.pass_context
def add_task(ctx: click.Context):
    server_name = ctx.obj["server_name"]
    try:
        _add_windows_task(server_name)
    except (click.Abort, KeyboardInterrupt, BSMError) as e:
        if isinstance(e, BSMError):
            logger.error(f"Failed to add task: {e}", exc_info=True)
        click.secho("\nAdd operation cancelled.", fg="yellow")


@schedule.command("delete")
@click.pass_context
def delete_task(ctx: click.Context):
    server_name = ctx.obj["server_name"]
    try:
        scheduler = WindowsTaskScheduler()
        tasks = scheduler.get_server_task_names(
            server_name, get_settings_instance().config_dir
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
                scheduler.delete_task(task_name_to_delete)
                if os.path.exists(file_path):
                    os.remove(file_path)
                click.secho("Task deleted successfully.", fg="green")
    except (click.Abort, KeyboardInterrupt):
        click.secho("\nDelete operation cancelled.", fg="yellow")


class WindowsTaskScheduler:
    XML_NAMESPACE: str = "{http://schemas.microsoft.com/windows/2004/02/mit/task}"

    def __init__(self) -> None:
        self.schtasks_cmd: str = shutil.which("schtasks")
        if not self.schtasks_cmd:
            raise CommandNotFoundError("schtasks")

    def get_task_info(self, task_names: List[str]) -> List[Dict[str, str]]:
        if not isinstance(task_names, list):
            return []
        if not task_names:
            return []
        task_info_list: List[Dict[str, str]] = []
        for task_name in task_names:
            if not task_name or not isinstance(task_name, str):
                continue
            try:
                result = subprocess.run(
                    [self.schtasks_cmd, "/Query", "/TN", task_name, "/XML"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                xml_output = result.stdout.strip()
                if xml_output.startswith("\ufeff"):
                    xml_output = xml_output[1:]
                root = ET.fromstring(xml_output)
                arguments_element = root.find(
                    f".//{self.XML_NAMESPACE}Actions/{self.XML_NAMESPACE}Exec/{self.XML_NAMESPACE}Arguments"
                )
                command_display = "N/A"
                if arguments_element is not None and arguments_element.text:
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
            except (subprocess.CalledProcessError, ET.ParseError):
                continue
        return task_info_list

    def _get_schedule_string(self, root: ET.Element) -> str:
        schedule_parts = []
        triggers_container = root.find(f".//{self.XML_NAMESPACE}Triggers")
        if triggers_container is None:
            return "No Triggers"
        for trigger in triggers_container:
            trigger_tag = trigger.tag.replace(self.XML_NAMESPACE, "")
            part = f"Unknown Trigger Type ({trigger_tag})"
            start_boundary_el = trigger.find(f".//{self.XML_NAMESPACE}StartBoundary")
            start_time_str = "UnknownTime"
            if start_boundary_el is not None and start_boundary_el.text:
                try:
                    start_time_str = datetime.fromisoformat(
                        start_boundary_el.text.strip()
                    ).strftime("%H:%M:%S")
                except ValueError:
                    if "T" in start_boundary_el.text:
                        start_time_str = start_boundary_el.text.split("T", 1)[-1]
            if trigger_tag == "TimeTrigger":
                part = f"One Time (at {start_time_str})"
            elif trigger_tag == "CalendarTrigger":
                schedule_by_day = trigger.find(f".//{self.XML_NAMESPACE}ScheduleByDay")
                schedule_by_week = trigger.find(
                    f".//{self.XML_NAMESPACE}ScheduleByWeek"
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
                        for day_el in days_of_week_el:
                            days_list.append(day_el.tag.replace(self.XML_NAMESPACE, ""))
                    days_str = ", ".join(days_list) if days_list else "AnyDay"
                    part = f"Weekly (every {interval} weeks on {days_str} at {start_time_str})"
                else:
                    part = f"CalendarTrigger (complex, at {start_time_str})"
            elif trigger_tag == "LogonTrigger":
                part = "On Logon"
            elif trigger_tag == "BootTrigger":
                part = "On System Startup"
            schedule_parts.append(part)
        return ", ".join(schedule_parts) if schedule_parts else "No Triggers"

    def get_server_task_names(
        self, server_name: str, config_dir: str
    ) -> List[Tuple[str, str]]:
        if not server_name:
            raise MissingArgumentError("Server name cannot be empty.")
        if not config_dir:
            raise MissingArgumentError("Config directory cannot be empty.")
        server_task_dir = os.path.join(config_dir, server_name)
        if not os.path.isdir(server_task_dir):
            return []
        task_files: List[Tuple[str, str]] = []
        try:
            for filename in os.listdir(server_task_dir):
                if filename.lower().endswith(".xml"):
                    file_path = os.path.join(server_task_dir, filename)
                    try:
                        tree = ET.parse(file_path)
                        uri_element = tree.find(
                            f"./{self.XML_NAMESPACE}RegistrationInfo/{self.XML_NAMESPACE}URI"
                        )
                        if uri_element is not None and uri_element.text:
                            task_name = uri_element.text.strip().lstrip("\\")
                            if task_name:
                                task_files.append((task_name, file_path))
                    except ET.ParseError:
                        continue
        except OSError as e:
            raise FileOperationError(
                f"Error reading tasks from directory '{server_task_dir}': {e}"
            ) from e
        return task_files

    def create_task_xml(
        self,
        server_name: str,
        command: str,
        command_args: str,
        task_name: str,
        config_dir: str,
        triggers: List[Dict[str, Any]],
        task_description: Optional[str] = None,
    ) -> str:
        if not all([server_name, command, task_name, config_dir]):
            raise MissingArgumentError("Required arguments cannot be empty.")
        if not isinstance(triggers, list):
            raise TypeError("Triggers must be a list of dictionaries.")
        if not EXPATH or not os.path.exists(EXPATH):
            raise AppFileNotFoundError(
                str(EXPATH), "Main script executable for task command"
            )
        effective_description = (
            task_description
            or f"Scheduled task for Bedrock Server Manager: server '{server_name}', command '{command}'."
        )
        try:
            task_attributes = {
                "version": "1.4",
                "xmlns": self.XML_NAMESPACE.strip("{}"),
            }
            task = ET.Element("Task", attrib=task_attributes)
            reg_info = ET.SubElement(task, "RegistrationInfo")
            ET.SubElement(reg_info, "Date").text = datetime.now().isoformat(
                timespec="seconds"
            )
            ET.SubElement(reg_info, "Author").text = (
                f"{os.getenv('USERDOMAIN', '')}\\{os.getenv('USERNAME', 'SYSTEM')}"
            )
            ET.SubElement(reg_info, "Description").text = effective_description
            ET.SubElement(reg_info, "URI").text = (
                task_name if task_name.startswith("\\") else f"\\{task_name}"
            )
            triggers_element = ET.SubElement(task, "Triggers")
            for trigger_data in triggers:
                self._add_trigger(triggers_element, trigger_data)
            principals = ET.SubElement(task, "Principals")
            principal = ET.SubElement(principals, "Principal", id="Author")
            ET.SubElement(principal, "UserId").text = os.getenv("USERNAME") or "SYSTEM"
            ET.SubElement(principal, "LogonType").text = "InteractiveToken"
            ET.SubElement(principal, "RunLevel").text = "LeastPrivilege"
            settings_el = ET.SubElement(task, "Settings")
            ET.SubElement(settings_el, "MultipleInstancesPolicy").text = "IgnoreNew"
            ET.SubElement(settings_el, "DisallowStartIfOnBatteries").text = "true"
            ET.SubElement(settings_el, "StopIfGoingOnBatteries").text = "true"
            ET.SubElement(settings_el, "AllowHardTerminate").text = "true"
            ET.SubElement(settings_el, "StartWhenAvailable").text = "false"
            ET.SubElement(settings_el, "ExecutionTimeLimit").text = "PT0S"
            ET.SubElement(settings_el, "Priority").text = "7"
            ET.SubElement(settings_el, "Enabled").text = "true"
            actions = ET.SubElement(task, "Actions", Context="Author")
            exec_action = ET.SubElement(actions, "Exec")
            ET.SubElement(exec_action, "Command").text = str(EXPATH)
            ET.SubElement(exec_action, "Arguments").text = (
                f"{command} {command_args}".strip()
            )
            server_config_dir = os.path.join(config_dir, server_name)
            os.makedirs(server_config_dir, exist_ok=True)
            safe_filename_base = task_name.replace("\\", "_").strip("_")
            safe_filename = re.sub(r'[/*?:"<>|]', "_", safe_filename_base) + ".xml"
            xml_file_path = os.path.join(server_config_dir, safe_filename)
            if hasattr(ET, "indent"):
                ET.indent(task)
            tree = ET.ElementTree(task)
            tree.write(xml_file_path, encoding="UTF-16", xml_declaration=True)
            return xml_file_path
        except Exception as e:
            raise FileOperationError(f"Unexpected error creating task XML: {e}") from e

    def import_task_from_xml(self, xml_file_path: str, task_name: str) -> None:
        if not xml_file_path:
            raise MissingArgumentError("XML file path cannot be empty.")
        if not task_name:
            raise MissingArgumentError("Task name cannot be empty.")
        if not os.path.isfile(xml_file_path):
            raise AppFileNotFoundError(xml_file_path, "Task XML file")
        try:
            tn_arg = task_name if task_name.startswith("\\") else f"\\{task_name}"
            subprocess.run(
                [
                    self.schtasks_cmd,
                    "/Create",
                    "/TN",
                    tn_arg,
                    "/XML",
                    xml_file_path,
                    "/F",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            stderr_msg = (e.stderr or "").strip()
            if "access is denied" in stderr_msg.lower():
                raise PermissionsError(
                    f"Access denied importing task '{task_name}'."
                ) from e
            raise SystemError(
                f"Failed to import task '{task_name}': {stderr_msg}"
            ) from e

    def delete_task(self, task_name: str) -> None:
        if not task_name:
            raise MissingArgumentError("Task name cannot be empty.")
        try:
            tn_arg = task_name if task_name.startswith("\\") else f"\\{task_name}"
            subprocess.run(
                [self.schtasks_cmd, "/Delete", "/TN", tn_arg, "/F"],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            stderr_msg = (e.stderr or "").strip().lower()
            if "the system cannot find the file specified" in stderr_msg:
                return
            if "access is denied" in stderr_msg:
                raise PermissionsError(
                    f"Access denied deleting task '{task_name}'."
                ) from e
            raise SystemError(
                f"Failed to delete task '{task_name}': {stderr_msg}"
            ) from e

    def _get_day_element_name(self, day_input: Any) -> str:
        day_str = str(day_input).strip().lower()
        mapping = {
            "sun": "Sunday",
            "sunday": "Sunday",
            "0": "Sunday",
            "7": "Sunday",
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
        raise UserInputError(f"Invalid day of week: '{day_input}'.")

    def _get_month_element_name(self, month_input: Any) -> str:
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
            "5": "May",
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
        if month_str in mapping:
            return mapping[month_str]
        raise UserInputError(f"Invalid month: '{month_input}'.")

    def _add_trigger(
        self, triggers_element: ET.Element, trigger_data: Dict[str, Any]
    ) -> None:
        trigger_type = trigger_data.get("type")
        start_boundary_iso = trigger_data.get("start")
        if not trigger_type:
            raise UserInputError("Trigger data must include a 'type' key.")
        if not start_boundary_iso and trigger_type in (
            "TimeTrigger",
            "Daily",
            "Weekly",
            "Monthly",
        ):
            raise UserInputError(
                f"Trigger type '{trigger_type}' requires a 'start' boundary."
            )
        common_trigger_elements = {f"{self.XML_NAMESPACE}Enabled": "true"}
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
                    raise UserInputError("Weekly trigger requires a list for 'days'.")
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
                days_of_month_input = trigger_data.get("days")
                months_input = trigger_data.get("months")
                if not days_of_month_input or not isinstance(days_of_month_input, list):
                    raise UserInputError("Monthly trigger requires a list for 'days'.")
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
                    )
                months_el = ET.SubElement(schedule, f"{self.XML_NAMESPACE}Months")
                for month_val in months_input:
                    ET.SubElement(
                        months_el,
                        f"{self.XML_NAMESPACE}{self._get_month_element_name(month_val)}",
                    )
        else:
            raise UserInputError(f"Unsupported trigger type: '{trigger_type}'.")


def create_task_name(server_name: str, command_args: str) -> str:
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    cleaned_args = re.sub(r"--server\s+\S+\s*", "", command_args).strip()
    sanitized = re.sub(r'[\\/*?:"<>|\s\-\.]+', "_", cleaned_args).strip("_")[:30]
    timestamp = get_timestamp()
    task_name = f"bedrock_{server_name}_{sanitized}_{timestamp}"
    return task_name.replace("\\", "_")


router = APIRouter(
    prefix="/windows_task_scheduler",
    tags=["Windows Task Scheduler"],
)


@router.get(
    "/schedule-tasks/{server_name}",
    response_class=HTMLResponse,
    tags=["plugin-ui"],
)
async def schedule_tasks_windows_page_route(
    request: Request,
    server_name: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    scheduler = WindowsTaskScheduler()
    task_names = scheduler.get_server_task_names(
        server_name, get_settings_instance().config_dir
    )
    tasks = scheduler.get_task_info([t[0] for t in task_names])
    return templates.TemplateResponse(
        "schedule_tasks_windows.html",
        {
            "request": request,
            "current_user": current_user,
            "server_name": server_name,
            "tasks": tasks,
            "error_message": None,
        },
    )


@router.get("/tasks/{server_name}", dependencies=[Depends(get_current_user)])
def get_server_tasks_api(
    server_name: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    scheduler = WindowsTaskScheduler()
    task_names = scheduler.get_server_task_names(
        server_name, get_settings_instance().config_dir
    )
    return scheduler.get_task_info([t[0] for t in task_names])


@router.post("/tasks", dependencies=[Depends(get_current_user)])
def create_task_api(
    task: Dict[str, Any], current_user: Dict[str, Any] = Depends(get_current_user)
):
    scheduler = WindowsTaskScheduler()
    task_name = create_task_name(task["server_name"], task["command"])
    xml_path = scheduler.create_task_xml(
        task["server_name"],
        task["command"],
        task["command_args"],
        task_name,
        get_settings_instance().config_dir,
        task["triggers"],
    )
    scheduler.import_task_from_xml(xml_path, task_name)
    return {"status": "success", "task_name": task_name}


@router.delete("/tasks/{task_name}")
def delete_task_api(
    task_name: str,
    task_file_path: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    scheduler = WindowsTaskScheduler()
    scheduler.delete_task(task_name)
    if os.path.exists(task_file_path):
        os.remove(task_file_path)
    return {"status": "success"}
