# src/bedrock_server_manager/core/system/__init__.py
"""Provide access to common system-level utilities, including process management,
resource monitoring, filesystem operations, and task scheduling abstractions.
"""

from .base import (
    ProcessResourceMonitor,
    check_internet_connectivity,
    delete_path_robustly,
    find_files,
)
from .base import is_server_running as is_bedrock_server_running
from .base import set_server_folder_permissions
from .process import (
    GuardedProcess,
    get_pid_file_path,
    get_verified_bedrock_process,
    is_process_running,
    read_pid_from_file,
    remove_pid_file_if_exists,
    write_pid_to_file,
)

__all__ = [
    # From base.py
    "check_internet_connectivity",
    "set_server_folder_permissions",
    "is_bedrock_server_running",
    "delete_path_robustly",
    "ProcessResourceMonitor",
    "find_files",
    # From process.py
    "GuardedProcess",
    "get_pid_file_path",
    "read_pid_from_file",
    "write_pid_to_file",
    "is_process_running",
    "remove_pid_file_if_exists",
    "get_verified_bedrock_process",
]
