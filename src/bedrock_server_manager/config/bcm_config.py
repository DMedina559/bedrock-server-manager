# bedrock_server_manager/config/bcm_config.py
"""
Manages the core application configuration file (bedrock_server_manager.json).

This module is responsible for handling a simple JSON configuration file that
stores essential startup settings like the data directory and database URL.
It uses the `appdirs` library to locate the appropriate user-specific
configuration directory in a cross-platform way.

The main components are:
- get_config_path(): Returns the path to the config file.
- load_config(): Reads the config file and returns its contents.
- save_config(data): Writes data to the config file.
"""

import json
import os
import logging
from typing import Dict, Any

from appdirs import user_config_dir

from .const import package_name, app_author

logger = logging.getLogger(__name__)

_CONFIG_FILE_NAME = "bedrock_server_manager.json"
_config_dir = user_config_dir(package_name)
_config_path = os.path.join(_config_dir, _CONFIG_FILE_NAME)


def get_config_path() -> str:
    """Returns the full, platform-specific path to the configuration file."""
    return _config_path


def load_config() -> Dict[str, Any]:
    """
    Loads the JSON configuration file, ensuring essential defaults are set.

    - If the file doesn't exist, it is created with default values.
    - If the file exists but lacks `data_dir` or `db_url`, the missing
      values are added and the file is saved.
    - The default `data_dir` is a user-specific data directory.

    Returns:
        Dict[str, Any]: The loaded and validated configuration data.
    """
    config = {}
    if os.path.exists(_config_path):
        try:
            with open(_config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to load configuration file at {_config_path}: {e}")
            # Continue with an empty config, the defaults will be applied.
            config = {}

    config_changed = False

    if "data_dir" not in config or not config["data_dir"]:
        # Fallback to a bedrock-server-manager folder in the user's home directory
        data_dir = os.path.join(os.path.expanduser("~"), f"{package_name}")
        config["data_dir"] = data_dir
        logger.info(f"Configuration 'data_dir' not set. Defaulting to {data_dir}.")
        config_changed = True

    if "db_url" not in config or not config["db_url"]:
        # Fallback to the defult database URL
        config_dir = os.path.join(config.get("data_dir"), ".config")
        os.makedirs(config_dir, exist_ok=True)
        default_db_url = (
            f"sqlite:///{os.path.join(config_dir, 'bedrock-server-manager.db')}"
        )
        config["db_url"] = default_db_url
        logger.info(f"Configuration 'db_url' not set. Defaulting to {default_db_url}.")
        config_changed = True

    if config_changed:
        save_config(config)

    return config


def save_config(data: Dict[str, Any]):
    """
    Saves the given data to the JSON configuration file.

    It ensures the configuration directory exists and writes the data
    with an indent for readability.

    Args:
        data (Dict[str, Any]): The configuration data to save.
    """
    try:
        os.makedirs(_config_dir, exist_ok=True)
        with open(_config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except OSError as e:
        logger.error(f"Failed to save configuration file at {_config_path}: {e}")


def get_config_value(key: str, default: Any = None) -> Any:
    """
    Retrieves a single value from the configuration file.

    Args:
        key (str): The key of the value to retrieve.
        default (Any, optional): The default value to return if the key is not found.

    Returns:
        Any: The configuration value or the default.
    """
    config = load_config()
    return config.get(key, default)


def set_config_value(key: str, value: Any):
    """
    Sets a single value in the configuration file.

    It loads the current config, updates the key with the new value,
    and then saves the entire configuration back to the file.

    Args:
        key (str): The key of the value to set.
        value (Any): The new value.
    """
    config = load_config()
    config[key] = value
    save_config(config)


from ..context import AppContext


def needs_setup(app_context: AppContext) -> bool:
    """
    Checks if the application needs to be set up by checking if there are any users in the database.
    """
    from ..db.models import User

    with app_context.db.session_manager() as db:
        return db.query(User).first() is None
