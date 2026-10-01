from . import api  # noqa: F401
from . import error as errors
from .config import get_installed_version
from .plugins import PluginBase, app_event, task_loop
from .web.deps.auth import (
    get_admin_user,
    get_current_user,
    get_current_user_optional,
    get_moderator_user,
)

__version__ = get_installed_version()

__all__ = [
    "errors",
    "__version__",
    "PluginBase",
    "app_event",
    "task_loop",
    "get_current_user_optional",
    "get_current_user",
    "get_admin_user",
    "get_moderator_user",
]
