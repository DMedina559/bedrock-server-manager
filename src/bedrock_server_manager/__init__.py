"""Public exports are lazy so core/event imports do not bootstrap APIs or HTTP."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

from . import error as errors
from .config.const import get_installed_version

if TYPE_CHECKING:
    from .plugins import PluginBase as PluginBase
    from .plugins.app_event import app_event as app_event
    from .plugins.settings import ExistingServerName as ExistingServerName
    from .plugins.task_loop import task_loop as task_loop

__version__ = get_installed_version()
_EXPORTS = {
    "PluginBase": ("plugins", "PluginBase"),
    "app_event": ("plugins", "app_event"),
    "task_loop": ("plugins", "task_loop"),
    "ExistingServerName": ("plugins.settings", "ExistingServerName"),
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
    "errors",
    "__version__",
    "PluginBase",
    "app_event",
    "task_loop",
    "ExistingServerName",
]
