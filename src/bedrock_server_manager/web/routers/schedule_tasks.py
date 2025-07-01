# bedrock_server_manager/web/routers/schedule_tasks.py
"""
FastAPI router for managing scheduled tasks related to Bedrock servers.

This module provides web endpoints (both HTML pages and JSON APIs) for
creating, viewing, modifying, and deleting scheduled tasks. It supports:
- Linux cron jobs via the :class:`~bedrock_server_manager.core.system.task_scheduler.LinuxTaskScheduler`.
- Windows Scheduled Tasks via the :class:`~bedrock_server_manager.core.system.task_scheduler.WindowsTaskScheduler`.

Functionality includes rendering pages to display current tasks and forms for
task manipulation, as well as API endpoints for programmatic control over
scheduled server actions (e.g., updates, backups, starts, stops).
Pydantic models are used for request and response validation.
Authentication and server validation are handled by FastAPI dependencies.
"""
import logging
import platform
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Request, Depends, HTTPException, status, Query, Path
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel, Field, validator

from bedrock_server_manager.web.templating import templates
from bedrock_server_manager.web.auth_utils import get_current_user
from ..dependencies import validate_server_exists  # Import the dependency
from bedrock_server_manager.api import task_scheduler as task_scheduler_api
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.config.const import EXPATH  # Used in Linux template
from bedrock_server_manager.error import BSMError, UserInputError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Scheduled Tasks"])  # No prefix


# --- Pydantic Models ---
class CronJobPayload(BaseModel):
    """
    Pydantic model for payloads related to adding or modifying Linux cron jobs.
    """

    new_cron_job: str = Field(
        ...,
        min_length=1,
        description="The new cron job string to be added or to replace an old one.",
    )
    old_cron_job: Optional[str] = Field(
        None,
        description="The existing cron job string to be modified. Required for modify operations.",
    )


class WindowsTaskTrigger(BaseModel):
    """
    Pydantic model representing a trigger for a Windows Scheduled Task.
    Used as part of the :class:`~.WindowsTaskPayload`.
    Aliases are used to match common representations of task trigger properties.
    """

    trigger_type: str = Field(
        ...,
        alias="Type",
        description="Type of the trigger (e.g., 'Daily', 'Weekly', 'OnLogon', 'OnEvent').",
    )
    start_time: Optional[str] = Field(
        None,
        alias="Time",
        description="Start time for time-based triggers (e.g., 'HH:MM').",
    )
    days_of_week: Optional[List[str]] = Field(
        None,
        alias="DaysOfWeek",
        description="List of days for weekly triggers (e.g., ['Monday', 'Friday']).",
    )
    event_id: Optional[int] = Field(
        None, alias="EventID", description="Event ID for 'OnEvent' triggers."
    )


class WindowsTaskPayload(BaseModel):
    """
    Pydantic model for payloads related to creating or modifying Windows Scheduled Tasks.
    """

    command: str = Field(
        ...,
        min_length=1,
        description="The base command to be executed (e.g., 'server update', 'backup create all').",
    )
    triggers: List[WindowsTaskTrigger] = Field(
        ...,
        description="A list of triggers that will start the task. Each trigger is defined by :class:`~.WindowsTaskTrigger`.",
    )


class GeneralTaskApiResponse(BaseModel):
    """
    Pydantic model for a generic API response from task scheduling operations.
    Provides status and optional details about the operation's outcome.
    """

    status: str = Field(
        ..., description="The status of the operation (e.g., 'success', 'error')."
    )
    message: Optional[str] = Field(
        None,
        description="A message providing more details about the operation's result.",
    )
    cron_jobs: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="A list of cron jobs, typically returned when fetching Linux tasks.",
    )
    tasks: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="A list of Windows tasks, typically returned when fetching Windows tasks.",
    )
    created_task_name: Optional[str] = Field(
        None, description="The name of the task that was created (Windows specific)."
    )
    new_task_name: Optional[str] = Field(
        None,
        description="The new name of a task if it was renamed during modification (Windows specific).",
    )


# --- HTML Routes ---
@router.get(
    "/schedule-tasks/{server_name}/linux",
    response_class=HTMLResponse,
    name="schedule_tasks_linux_page",
)
async def schedule_tasks_linux_page_route(
    request: Request,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Serves the HTML page for managing Linux cron jobs for a specific server.

    This page displays existing cron jobs associated with the server and provides
    functionality to add, modify, or delete them. It only renders if the
    underlying system is Linux and cron scheduling is supported.

    Args:
        request (Request): The incoming FastAPI request object.
        server_name (str): The name of the server, validated by `validate_server_exists`.
                           Injected by FastAPI.
        current_user (Dict[str, Any]): The authenticated user object, injected by
                                       `get_current_user`.

    Returns:
        HTMLResponse: Renders the `schedule_tasks.html` template with cron job data.
        RedirectResponse: If the system is not Linux or an error occurs, redirects
                          to the main page with an error message.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"User '{identity}' accessed Linux cron schedule page for server '{server_name}'."
    )

    if not isinstance(
        task_scheduler_api.scheduler, task_scheduler_api.core_task.LinuxTaskScheduler
    ):
        msg = "Cron job scheduling is only available on supported Linux systems."
        return RedirectResponse(
            url=f"/?message={msg}&category=warning", status_code=status.HTTP_302_FOUND
        )

    table_data = []
    error_message: Optional[str] = None
    try:
        cron_jobs_response = task_scheduler_api.get_server_cron_jobs(server_name)
        if cron_jobs_response.get("status") == "error":
            error_message = (
                f"Error retrieving cron jobs: {cron_jobs_response.get('message')}"
            )
        else:
            cron_jobs_list = cron_jobs_response.get("cron_jobs", [])
            if cron_jobs_list:
                table_response = task_scheduler_api.get_cron_jobs_table(cron_jobs_list)
                if table_response.get("status") == "error":
                    error_message = (
                        f"Error formatting cron jobs: {table_response.get('message')}"
                    )
                else:
                    table_data = table_response.get("table_data", [])
    except Exception as e:
        error_message = "An unexpected error occurred while loading scheduled tasks."
        logger.error(
            f"Unexpected error on Linux scheduler page for '{server_name}': {e}",
            exc_info=True,
        )

    return templates.TemplateResponse(
        "schedule_tasks.html",
        {
            "request": request,
            "current_user": current_user,
            "server_name": server_name,
            "table_data": table_data,
            "EXPATH": EXPATH,
            "error_message": error_message,
        },
    )


@router.get(
    "/schedule-tasks/{server_name}/windows",
    response_class=HTMLResponse,
    name="schedule_tasks_windows_page",
)
async def schedule_tasks_windows_page_route(
    request: Request,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Serves the HTML page for managing Windows Scheduled Tasks for a specific server.

    This page displays existing Windows Scheduled Tasks associated with the server
    and provides functionality to add, modify, or delete them. It only renders
    if the underlying system is Windows and Task Scheduler is supported.

    Args:
        request (Request): The incoming FastAPI request object.
        server_name (str): The name of the server, validated by `validate_server_exists`.
                           Injected by FastAPI.
        current_user (Dict[str, Any]): The authenticated user object, injected by
                                       `get_current_user`.

    Returns:
        HTMLResponse: Renders the `schedule_tasks_windows.html` template with task data.
        RedirectResponse: If the system is not Windows or an error occurs, redirects
                          to the main page with an error message.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"User '{identity}' accessed Windows Task Scheduler page for '{server_name}'."
    )

    if not isinstance(
        task_scheduler_api.scheduler, task_scheduler_api.core_task.WindowsTaskScheduler
    ):
        msg = "Windows Task Scheduling is only available on supported Windows systems."
        return RedirectResponse(
            url=f"/?message={msg}&category=warning", status_code=status.HTTP_302_FOUND
        )

    tasks = []
    error_message: Optional[str] = None
    try:
        config_dir = settings.config_dir
        if not config_dir:
            raise BSMError("Base configuration directory not set.")

        task_names_resp = task_scheduler_api.get_server_task_names(
            server_name, config_dir
        )
        if task_names_resp.get("status") == "error":
            error_message = (
                f"Error retrieving task files: {task_names_resp.get('message')}"
            )
        else:
            task_names = [t[0] for t in task_names_resp.get("task_names", [])]
            if task_names:
                task_info_resp = task_scheduler_api.get_windows_task_info(task_names)
                if task_info_resp.get("status") == "error":
                    error_message = f"Error retrieving task details: {task_info_resp.get('message')}"
                else:
                    tasks = task_info_resp.get("task_info", [])
    except Exception as e:
        error_message = "An unexpected error occurred while loading scheduled tasks."
        logger.error(
            f"Error on Windows scheduler page for '{server_name}': {e}", exc_info=True
        )

    return templates.TemplateResponse(
        "schedule_tasks_windows.html",
        {
            "request": request,
            "current_user": current_user,
            "server_name": server_name,
            "tasks": tasks,
            "error_message": error_message,
        },
    )


# --- API Routes (Linux Cron) ---
@router.post(
    "/api/server/{server_name}/cron_scheduler/add",
    response_model=GeneralTaskApiResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Scheduled Tasks API - Linux"],
)
async def add_cron_job_api_route(
    payload: CronJobPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    API endpoint to add a new Linux cron job.

    This endpoint is only functional on Linux systems with cron support.
    It takes a cron string and adds it to the system's crontab.

    Args:
        payload (CronJobPayload): Pydantic model containing the `new_cron_job` string.
        server_name (str): The name of the server (context for logging/validation),
                           validated by `validate_server_exists`. Injected by FastAPI.
        current_user (Dict[str, Any]): The authenticated user object, injected by
                                       `get_current_user`.

    Returns:
        GeneralTaskApiResponse: JSON response indicating success or failure.
                                On success, status is 201.

    Raises:
        HTTPException:
            - 400 (Bad Request): If input is invalid (e.g., bad cron string format).
            - 403 (Forbidden): If the system is not Linux.
            - 500 (Internal Server Error): For other errors during cron job addition.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Add cron job request by '{identity}' (context: '{server_name}'). Cron: {payload.new_cron_job}"
    )

    if not isinstance(
        task_scheduler_api.scheduler, task_scheduler_api.core_task.LinuxTaskScheduler
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cron job operations are only supported on Linux.",
        )

    try:
        result = task_scheduler_api.add_cron_job(payload.new_cron_job)
        if result.get("status") == "success":
            return GeneralTaskApiResponse(
                status="success", message=result.get("message")
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Failed to add cron job."),
            )
    except UserInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        logger.error(
            f"API Add Cron Job for server '{server_name}': BSMError: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"API Add Cron Job for server '{server_name}': Unexpected error: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )


@router.post(
    "/api/server/{server_name}/cron_scheduler/modify",
    response_model=GeneralTaskApiResponse,
    tags=["Scheduled Tasks API - Linux"],
)
async def modify_cron_job_api_route(
    payload: CronJobPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    API endpoint to modify an existing Linux cron job.

    This endpoint is only functional on Linux systems with cron support.
    It replaces an `old_cron_job` string with a `new_cron_job` string in the crontab.

    Args:
        payload (CronJobPayload): Pydantic model containing `old_cron_job`
                                  and `new_cron_job` strings.
        server_name (str): The name of the server (context for logging/validation),
                           validated by `validate_server_exists`. Injected by FastAPI.
        current_user (Dict[str, Any]): The authenticated user object, injected by
                                       `get_current_user`.

    Returns:
        GeneralTaskApiResponse: JSON response indicating success or failure.

    Raises:
        HTTPException:
            - 400 (Bad Request): If `old_cron_job` is missing or input is invalid.
            - 403 (Forbidden): If the system is not Linux.
            - 404 (Not Found): If the `old_cron_job` is not found in the crontab.
            - 500 (Internal Server Error): For other errors during cron job modification.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Modify cron job request by '{identity}' (context: '{server_name}')."
    )

    if not isinstance(
        task_scheduler_api.scheduler, task_scheduler_api.core_task.LinuxTaskScheduler
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cron job operations are only supported on Linux.",
        )

    if not payload.old_cron_job:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'old_cron_job' is required for modification.",
        )

    try:
        result = task_scheduler_api.modify_cron_job(
            payload.old_cron_job, payload.new_cron_job
        )
        if result.get("status") == "success":
            return GeneralTaskApiResponse(
                status="success", message=result.get("message")
            )
        else:
            detail = result.get("message", "Failed to modify cron job.")
            status_code_err = (
                status.HTTP_404_NOT_FOUND
                if "not found" in detail.lower()
                else status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            raise HTTPException(status_code=status_code_err, detail=detail)
    except UserInputError as e:
        status_code_err = (
            status.HTTP_404_NOT_FOUND
            if "not found" in str(e).lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code_err, detail=str(e))
    except BSMError as e:
        logger.error(
            f"API Modify Cron Job for server '{server_name}': BSMError: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"API Modify Cron Job for server '{server_name}': Unexpected error: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )


@router.delete(
    "/api/server/{server_name}/cron_scheduler/delete",
    response_model=GeneralTaskApiResponse,
    tags=["Scheduled Tasks API - Linux"],
)
async def delete_cron_job_api_route(
    cron_string: str = Query(
        ..., min_length=1, description="The exact cron string of the job to delete."
    ),
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    API endpoint to delete an existing Linux cron job.

    This endpoint is only functional on Linux systems with cron support.
    It removes a cron job matching the provided `cron_string` from the crontab.

    Args:
        cron_string (str): The exact cron string of the job to delete.
                           Provided as a query parameter.
        server_name (str): The name of the server (context for logging/validation),
                           validated by `validate_server_exists`. Injected by FastAPI.
        current_user (Dict[str, Any]): The authenticated user object, injected by
                                       `get_current_user`.

    Returns:
        GeneralTaskApiResponse: JSON response indicating success or failure.

    Raises:
        HTTPException:
            - 400 (Bad Request): If `cron_string` is missing or invalid.
            - 403 (Forbidden): If the system is not Linux.
            - 404 (Not Found): If the specified `cron_string` is not found.
            - 500 (Internal Server Error): For other errors during cron job deletion.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Delete cron job request by '{identity}' (context: '{server_name}'). Cron: {cron_string}"
    )

    if not isinstance(
        task_scheduler_api.scheduler, task_scheduler_api.core_task.LinuxTaskScheduler
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cron job operations are only supported on Linux.",
        )

    try:
        result = task_scheduler_api.delete_cron_job(cron_string)
        if result.get("status") == "success":
            return GeneralTaskApiResponse(
                status="success", message=result.get("message")
            )
        else:
            detail = result.get("message", "Failed to delete cron job.")
            status_code_err = (
                status.HTTP_404_NOT_FOUND
                if "not found" in detail.lower()
                else status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            raise HTTPException(status_code=status_code_err, detail=detail)
    except UserInputError as e:
        status_code_err = (
            status.HTTP_404_NOT_FOUND
            if "not found" in str(e).lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code_err, detail=str(e))
    except BSMError as e:
        logger.error(
            f"API Delete Cron Job for server '{server_name}': BSMError: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"API Delete Cron Job for server '{server_name}': Unexpected error: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )


# --- API Routes (Windows Scheduled Tasks) ---
@router.post(
    "/api/server/{server_name}/task_scheduler/add",
    response_model=GeneralTaskApiResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Scheduled Tasks API - Windows"],
)
async def add_windows_task_api_route(
    payload: WindowsTaskPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    API endpoint to add a new Windows Scheduled Task.

    This endpoint is only functional on Windows systems with Task Scheduler support.
    It creates a new scheduled task based on the provided command and triggers.
    A configuration file for the task is also stored by the application.

    Args:
        payload (WindowsTaskPayload): Pydantic model containing `command` and `triggers`.
        server_name (str): The name of the server, validated by `validate_server_exists`.
                           Used to construct task name and command arguments. Injected by FastAPI.
        current_user (Dict[str, Any]): The authenticated user object, injected by
                                       `get_current_user`.

    Returns:
        GeneralTaskApiResponse: JSON response indicating success or failure, including
                                the `created_task_name`. On success, status is 201.

    Raises:
        HTTPException:
            - 400 (Bad Request): If the command is invalid or input is malformed.
            - 403 (Forbidden): If the system is not Windows.
            - 500 (Internal Server Error): If the configuration directory is not set
              or for other errors during task creation.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Add Windows task request by '{identity}' for server '{server_name}'. Command: {payload.command}"
    )

    if not isinstance(
        task_scheduler_api.scheduler, task_scheduler_api.core_task.WindowsTaskScheduler
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Windows Scheduled Tasks are only supported on Windows.",
        )

    valid_commands = [
        "server update",
        "backup create all",
        "server start",
        "server stop",
        "server restart",
    ]
    if payload.command not in valid_commands:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid command. Must be one of: {valid_commands}.",
        )

    try:
        config_dir = settings.config_dir
        if not config_dir:
            raise BSMError("Base configuration directory not set.")

        command_args = f"--server {server_name}"
        if payload.command == "players scan":
            command_args = ""
        task_name = task_scheduler_api.create_task_name(
            server_name, command_args=payload.command
        )

        result = task_scheduler_api.create_windows_task(
            server_name=server_name,
            command=payload.command,
            command_args=command_args,
            task_name=task_name,
            triggers=payload.triggers,
            config_dir=config_dir,
        )

        if result.get("status") == "success":
            return GeneralTaskApiResponse(
                status="success",
                message=result.get("message"),
                created_task_name=task_name,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Failed to create Windows task."),
            )

    except UserInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        logger.error(
            f"API Add Windows Task for '{server_name}': BSMError: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"API Add Windows Task for '{server_name}': Unexpected error: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )


@router.put(
    "/api/server/{server_name}/task_scheduler/task/{task_name:path}",
    response_model=GeneralTaskApiResponse,
    tags=["Scheduled Tasks API - Windows"],
)
async def modify_windows_task_api_route(
    server_name: str,
    payload: WindowsTaskPayload,
    task_name: str = Path(
        ..., description="The full name of the task, potentially including backslashes."
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    API endpoint to modify an existing Windows Scheduled Task.

    This endpoint is only functional on Windows systems. It updates the specified
    task with a new command and/or triggers. The task may be renamed if the
    command changes in a way that affects the standard naming convention.
    The application's stored configuration file for the task is also updated.

    Args:
        server_name (str): The name of the server associated with the task.
                           Validated by `validate_server_exists` (implicitly, as it's part of the path
                           but not directly a `Depends` on this route, relying on overall structure).
        payload (WindowsTaskPayload): Pydantic model with the new `command` and `triggers`.
        task_name (str): The full name of the task to modify (e.g., "BSM\\MyServer\\Update").
                         Provided as a path parameter.
        current_user (Dict[str, Any]): The authenticated user object, injected by `get_current_user`.

    Returns:
        GeneralTaskApiResponse: JSON response indicating success or failure.
                                May include `new_task_name` if the task was renamed.

    Raises:
        HTTPException:
            - 400 (Bad Request): If the command is invalid or input is malformed.
            - 403 (Forbidden): If the system is not Windows.
            - 404 (Not Found): If the original `task_name` is not found.
            - 500 (Internal Server Error): If config dir not set or other modification errors.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Modify Windows task '{task_name}' request by '{identity}' for server '{server_name}'."
    )

    if not isinstance(
        task_scheduler_api.scheduler, task_scheduler_api.core_task.WindowsTaskScheduler
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Windows Scheduled Tasks are only supported on Windows.",
        )

    # Define valid commands for the task
    valid_commands = [
        "server update",
        "backup create all",
        "server start",
        "server stop",
        "server restart",
        "scan-players",
    ]
    if payload.command not in valid_commands:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid command. Must be one of: {valid_commands}.",
        )

    try:
        config_dir = settings.config_dir
        if not config_dir:
            raise BSMError("Base configuration directory not set.")

        # Determine command arguments based on the command
        command_args = f"--server {server_name}"
        if payload.command == "players scan":
            command_args = ""

        # Create a new task name based on server and command
        new_task_name_str = task_scheduler_api.create_task_name(
            server_name, command_args=payload.command
        )

        # Call the core API to modify the Windows task
        result = task_scheduler_api.modify_windows_task(
            old_task_name=task_name,
            server_name=server_name,
            command=payload.command,
            command_args=command_args,
            new_task_name=new_task_name_str,
            triggers=payload.triggers,
            config_dir=config_dir,
        )

        # Handle the result of the modification
        if result.get("status") == "success":
            return GeneralTaskApiResponse(
                status="success",
                message=result.get("message"),
                new_task_name=new_task_name_str,
            )
        else:
            detail = result.get("message", "Failed to modify Windows task.")
            status_code_err = (
                status.HTTP_404_NOT_FOUND
                if "not found" in detail.lower()
                else status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            raise HTTPException(status_code=status_code_err, detail=detail)

    except UserInputError as e:
        # Handle errors related to invalid user input
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        # Handle application-specific errors
        logger.error(
            f"API Modify Windows Task '{task_name}' for '{server_name}': BSMError: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        # Catch any other unexpected errors
        logger.error(
            f"API Modify Windows Task '{task_name}' for '{server_name}': Unexpected error: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )


@router.delete(
    "/api/server/{server_name}/task_scheduler/task/{task_name:path}",
    response_model=GeneralTaskApiResponse,
    tags=["Scheduled Tasks API - Windows"],
)
async def delete_windows_task_api_route(
    server_name: str,
    task_name: str = Path(..., description="The full name of the task to delete."),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    API endpoint to delete an existing Windows Scheduled Task.

    This endpoint is only functional on Windows systems. It removes the specified
    task from the Windows Task Scheduler and deletes its corresponding
    configuration file stored by the application.

    Args:
        server_name (str): The name of the server associated with the task.
                           (Used for context and locating task config).
        task_name (str): The full name of the task to delete (e.g., "BSM\\MyServer\\Update").
                         Provided as a path parameter.
        current_user (Dict[str, Any]): The authenticated user object, injected by
                                       `get_current_user`.

    Returns:
        GeneralTaskApiResponse: JSON response indicating success or failure.

    Raises:
        HTTPException:
            - 403 (Forbidden): If the system is not Windows.
            - 404 (Not Found): If the task or its configuration file is not found.
            - 500 (Internal Server Error): If config dir not set or other deletion errors.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Delete Windows task '{task_name}' request by '{identity}' for server '{server_name}'."
    )

    if not isinstance(
        task_scheduler_api.scheduler, task_scheduler_api.core_task.WindowsTaskScheduler
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Windows Scheduled Tasks are only supported on Windows.",
        )

    try:
        config_dir = settings.config_dir
        if not config_dir:
            raise BSMError("Base configuration directory not set.")

        task_list_resp = task_scheduler_api.get_server_task_names(
            server_name, config_dir
        )
        if task_list_resp.get("status") != "success":
            raise BSMError(
                f"Could not list tasks to find '{task_name}' for deletion: {task_list_resp.get('message')}"
            )

        task_file_path = next(
            (
                path
                for name, path in task_list_resp.get("task_names", [])
                if name.lstrip("\\") == task_name.lstrip("\\")
            ),
            None,
        )

        if not task_file_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task configuration file for '{task_name}' not found.",
            )

        result = task_scheduler_api.delete_windows_task(task_name, task_file_path)
        if result.get("status") == "success":
            return GeneralTaskApiResponse(
                status="success", message=result.get("message")
            )
        else:
            detail = result.get("message", "Failed to delete Windows task.")
            status_code_err = (
                status.HTTP_404_NOT_FOUND
                if "not found" in detail.lower()
                else status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            raise HTTPException(status_code=status_code_err, detail=detail)

    except UserInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        logger.error(
            f"API Delete Windows Task '{task_name}' for '{server_name}': BSMError: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"API Delete Windows Task '{task_name}' for '{server_name}': Unexpected error: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )
