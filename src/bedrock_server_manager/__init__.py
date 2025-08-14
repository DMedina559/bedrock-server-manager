# bedrock_server_manager/__init__.py
# Core classes
from .core import (
    BedrockServerManager,
    BedrockServer,
    BedrockDownloader,
    BedrockProcessManager,
)

# Configuration
from .config import Settings, get_installed_version

# App Context
from .context import AppContext

# Plugin system essentials
from .plugins import PluginBase, PluginManager
from . import error as errors

# --- Version ---
__version__ = get_installed_version()

__all__ = [
    # Core
    "BedrockServerManager",
    "BedrockServer",
    "BedrockDownloader",
    "BedrockProcessManager",
    # Config
    "Settings",
    # App Context
    "AppContext",
    # Plugins
    "PluginBase",
    "PluginManager",
    # Errors
    "errors",
    # Version
    "__version__",
]
