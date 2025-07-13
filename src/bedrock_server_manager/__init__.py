# bedrock_server_manager/__init__.py
import logging

# Core classes
from .core import BedrockServerManager, BedrockServer, BedrockDownloader

# Configuration
from .config import settings, Settings, get_installed_version

# Plugin system essentials
from .plugins import PluginBase, PluginManager
from . import error as errors

# --- Version ---
__version__ = get_installed_version()

# --- Global Instances ---
plugin_manager = PluginManager()

__all__ = [
    # Core
    "BedrockServerManager",
    "BedrockServer",
    "BedrockDownloader",
    # Config
    "settings",  # The global instance
    "Settings",  # The class
    # Plugins
    "PluginBase",
    "plugin_manager",  # The global instance
    # Errors
    "errors",
    # Version
    "__version__",
]

logger = logging.getLogger(__name__)

# --- Initialize API bridge and load plugins ---
from . import api as _api_module_for_init
