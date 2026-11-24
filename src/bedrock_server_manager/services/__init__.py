# src/bedrock_server_manager/services/__init__.py
"""
Services subpackage providing domain business logic and mutation abstractions.
"""

from typing import TYPE_CHECKING

from .metrics_service import MetricsService, ResourceMonitor
from .plugin_service import PluginService
from .server_service import ServerService
from .settings_service import SettingsService
from .user_service import UserService

if TYPE_CHECKING:
    from .task_service import TaskManager, TaskRecord

__all__ = [
    "MetricsService",
    "PluginService",
    "ResourceMonitor",
    "ServerService",
    "SettingsService",
    "TaskManager",
    "TaskRecord",
    "UserService",
]


def __getattr__(name: str):
    if name in {"TaskManager", "TaskRecord"}:
        from .task_service import TaskManager, TaskRecord

        return TaskManager if name == "TaskManager" else TaskRecord
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
