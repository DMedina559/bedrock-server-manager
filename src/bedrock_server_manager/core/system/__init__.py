# src/bedrock_server_manager/core/system/__init__.py
"""
Provides access to common system-level utilities, including process management,
resource monitoring, filesystem operations, and task scheduling abstractions.
"""

from .base import (
    ResourceMonitor,
    can_manage_services,
    can_manage_services_async,
    check_internet_connectivity,
    check_internet_connectivity_async,
    delete_path_robustly,
    delete_path_robustly_async,
    find_files,
    find_files_async,
)
from .base import is_server_running as is_bedrock_server_running
from .base import is_server_running_async as is_bedrock_server_running_async
from .base import set_server_folder_permissions, set_server_folder_permissions_async
from .linux import check_service_exists as check_linux_service_exists
from .linux import check_service_exists_async as check_linux_service_exists_async
from .linux import (
    create_systemd_service_file,
    create_systemd_service_file_async,
    disable_systemd_service,
    disable_systemd_service_async,
    enable_systemd_service,
    enable_systemd_service_async,
    get_systemd_service_file_path,
    get_systemd_service_file_path_async,
)
from .process import (
    GuardedProcess,
    get_bedrock_launcher_pid_file_path,
    get_bedrock_launcher_pid_file_path_async,
    get_bedrock_server_pid_file_path,
    get_bedrock_server_pid_file_path_async,
    get_pid_file_path,
    get_pid_file_path_async,
    get_verified_bedrock_process,
    get_verified_bedrock_process_async,
    is_process_running,
    is_process_running_async,
    launch_detached_process,
    launch_detached_process_async,
    read_pid_from_file,
    read_pid_from_file_async,
    remove_pid_file_if_exists,
    remove_pid_file_if_exists_async,
    terminate_process_by_pid,
    terminate_process_by_pid_async,
    verify_process_identity,
    verify_process_identity_async,
    write_pid_to_file,
    write_pid_to_file_async,
)
from .windows import check_service_exists as check_windows_service_exists
from .windows import check_service_exists_async as check_windows_service_exists_async
from .windows import (
    create_windows_service,
    create_windows_service_async,
    delete_windows_service,
    delete_windows_service_async,
    disable_windows_service,
    disable_windows_service_async,
    enable_windows_service,
    enable_windows_service_async,
)

__all__ = [
    # From base.py
    "check_internet_connectivity",
    "check_internet_connectivity_async",
    "set_server_folder_permissions",
    "set_server_folder_permissions_async",
    "is_bedrock_server_running",
    "is_bedrock_server_running_async",
    "delete_path_robustly",
    "delete_path_robustly_async",
    "ResourceMonitor",
    "find_files",
    "find_files_async",
    "can_manage_services",
    "can_manage_services_async",
    # From process.py
    "GuardedProcess",
    "get_pid_file_path",
    "get_pid_file_path_async",
    "get_bedrock_launcher_pid_file_path",
    "get_bedrock_launcher_pid_file_path_async",
    "get_bedrock_server_pid_file_path",
    "get_bedrock_server_pid_file_path_async",
    "read_pid_from_file",
    "read_pid_from_file_async",
    "write_pid_to_file",
    "write_pid_to_file_async",
    "is_process_running",
    "is_process_running_async",
    "launch_detached_process",
    "launch_detached_process_async",
    "terminate_process_by_pid",
    "terminate_process_by_pid_async",
    "remove_pid_file_if_exists",
    "remove_pid_file_if_exists_async",
    "get_verified_bedrock_process",
    "get_verified_bedrock_process_async",
    "verify_process_identity",
    "verify_process_identity_async",
    # From linux.py
    "get_systemd_service_file_path",
    "get_systemd_service_file_path_async",
    "check_linux_service_exists",
    "check_linux_service_exists_async",
    "create_systemd_service_file",
    "create_systemd_service_file_async",
    "enable_systemd_service",
    "enable_systemd_service_async",
    "disable_systemd_service",
    "disable_systemd_service_async",
    # From windows.py
    "check_windows_service_exists",
    "check_windows_service_exists_async",
    "create_windows_service",
    "create_windows_service_async",
    "enable_windows_service",
    "enable_windows_service_async",
    "disable_windows_service",
    "disable_windows_service_async",
    "delete_windows_service",
    "delete_windows_service_async",
]
