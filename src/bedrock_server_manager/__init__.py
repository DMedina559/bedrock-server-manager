"""Public exports are lazy so core/event imports do not bootstrap APIs or HTTP."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

from . import error as errors
from .config.const import get_installed_version

if TYPE_CHECKING:
    from . import api as api
    from .backups.contents import DEFAULT_COMPONENTS as DEFAULT_COMPONENTS
    from .backups.contents import BackupComponents as BackupComponents
    from .backups.contents import BackupContentSelection as BackupContentSelection
    from .backups.contents import BackupMode as BackupMode
    from .backups.contents import SelectableComponent as SelectableComponent
    from .events import CancellableEvent as CancellableEvent
    from .events import EventActivityQuery as EventActivityQuery
    from .events import EventFilter as EventFilter
    from .events import EventNotification as EventNotification
    from .events import OperationActivity as OperationActivity
    from .events import OperationActivityQuery as OperationActivityQuery
    from .events import OperationName as OperationName
    from .events import OperationResultQuery as OperationResultQuery
    from .events import OperationSequence as OperationSequence
    from .events import OperationSnapshot as OperationSnapshot
    from .events import PluginEvent as PluginEvent
    from .plugins import PluginBase as PluginBase
    from .plugins.app_event import app_event as app_event
    from .plugins.settings import ExistingServerName as ExistingServerName
    from .plugins.task_loop import task_loop as task_loop
    from .web.deps.auth import get_admin_user as get_admin_user
    from .web.deps.auth import get_current_user as get_current_user
    from .web.deps.auth import get_current_user_optional as get_current_user_optional
    from .web.deps.auth import get_moderator_user as get_moderator_user
    from .web.schemas import BaseApiResponse as BaseApiResponse
    from .web.schemas import TaskAcceptedResponse as TaskAcceptedResponse
    from .web.schemas import UserResponse as UserResponse

__version__ = get_installed_version()
_EXPORTS = {
    "PluginBase": ("plugins", "PluginBase"),
    "app_event": ("plugins", "app_event"),
    "task_loop": ("plugins", "task_loop"),
    "ExistingServerName": ("plugins.settings", "ExistingServerName"),
    # Event & Operation types for plugins
    "CancellableEvent": ("events", "CancellableEvent"),
    "EventActivityQuery": ("events", "EventActivityQuery"),
    "EventFilter": ("events", "EventFilter"),
    "EventNotification": ("events", "EventNotification"),
    "PluginEvent": ("events", "PluginEvent"),
    "OperationActivity": ("events.operations", "OperationActivity"),
    "OperationActivityQuery": ("events.operations", "OperationActivityQuery"),
    "OperationName": ("events.operations", "OperationName"),
    "OperationResultQuery": ("events.operations", "OperationResultQuery"),
    "OperationSequence": ("events.operations", "OperationSequence"),
    "OperationSnapshot": ("events.operations", "OperationSnapshot"),
    # Backup content selection types for plugin settings
    "BackupComponents": ("backups.contents", "BackupComponents"),
    "BackupContentSelection": ("backups.contents", "BackupContentSelection"),
    "BackupMode": ("backups.contents", "BackupMode"),
    "DEFAULT_COMPONENTS": ("backups.contents", "DEFAULT_COMPONENTS"),
    "SelectableComponent": ("backups.contents", "SelectableComponent"),
    # Web auth dependencies & schemas for plugin FastAPI routers
    "get_admin_user": ("web.deps.auth", "get_admin_user"),
    "get_current_user": ("web.deps.auth", "get_current_user"),
    "get_current_user_optional": ("web.deps.auth", "get_current_user_optional"),
    "get_moderator_user": ("web.deps.auth", "get_moderator_user"),
    "BaseApiResponse": ("web.schemas", "BaseApiResponse"),
    "TaskAcceptedResponse": ("web.schemas", "TaskAcceptedResponse"),
    "UserResponse": ("web.schemas", "UserResponse"),
}


def __getattr__(name: str) -> Any:
    if name == "api":
        value = import_module(".api", __name__)
    elif name in _EXPORTS:
        module, attribute = _EXPORTS[name]
        value = getattr(import_module("." + module, __name__), attribute)
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    globals()[name] = value
    return value


__all__ = [
    "api",
    "errors",
    "__version__",
    "PluginBase",
    "app_event",
    "task_loop",
    "ExistingServerName",
    "CancellableEvent",
    "EventActivityQuery",
    "EventFilter",
    "EventNotification",
    "PluginEvent",
    "OperationActivity",
    "OperationActivityQuery",
    "OperationName",
    "OperationResultQuery",
    "OperationSequence",
    "OperationSnapshot",
    "BackupComponents",
    "BackupContentSelection",
    "BackupMode",
    "DEFAULT_COMPONENTS",
    "SelectableComponent",
    "get_admin_user",
    "get_current_user",
    "get_current_user_optional",
    "get_moderator_user",
    "BaseApiResponse",
    "TaskAcceptedResponse",
    "UserResponse",
]
