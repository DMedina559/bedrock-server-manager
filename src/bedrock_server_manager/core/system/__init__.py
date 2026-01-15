# src/bedrock_server_manager/core/system/__init__.py
"""
Provides access to common system-level utilities, including process management,
resource monitoring, filesystem operations, and task scheduling abstractions.
"""

from .base import ResourceMonitor, check_internet_connectivity, delete_path_robustly
from .base import is_server_running as is_bedrock_server_running
from .base import set_server_folder_permissions
from .process import (
    GuardedProcess,
    get_bedrock_launcher_pid_file_path,
    get_pid_file_path,
    get_verified_bedrock_process,
    is_process_running,
    launch_detached_process,
    read_pid_from_file,
    remove_pid_file_if_exists,
    terminate_process_by_pid,
    write_pid_to_file,
)
from .task_scheduler import get_task_scheduler

__all__ = [
    # From base.py
    "check_internet_connectivity",
    "set_server_folder_permissions",
    "is_bedrock_server_running",
    "delete_path_robustly",
    "ResourceMonitor",
    # From process.py
    "GuardedProcess",
    "get_pid_file_path",
    "get_bedrock_launcher_pid_file_path",
    "read_pid_from_file",
    "write_pid_to_file",
    "is_process_running",
    "launch_detached_process",
    "terminate_process_by_pid",
    "remove_pid_file_if_exists",
    "get_verified_bedrock_process",
    # From task_scheduler.py
    "get_task_scheduler",
]
