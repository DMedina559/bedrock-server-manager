# bedrock_server_manager/config/bcm_config.py
"""Resolve and persist bootstrap configuration in JSON."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from typing import Any, Dict

from platformdirs import user_config_dir
from pydantic import ValidationError

from ..error import ConfigurationError
from ..logging import log_operation_error
from .const import CONFIG_FILE_NAME, env_name, package_name
from .models import BootstrapConfig

logger = logging.getLogger(__name__)


_config_write_lock = threading.RLock()

_custom_config_dir: str | None = None
_custom_data_dir: str | None = None
_custom_log_level: str | None = None
_custom_db_url: str | None = None


def set_custom_config_dir(path: str | None) -> None:
    global _custom_config_dir
    _custom_config_dir = path


def set_custom_data_dir(path: str | None) -> None:
    global _custom_data_dir
    _custom_data_dir = path


def set_custom_db_url(url: str | None) -> None:
    global _custom_db_url
    _custom_db_url = url


def set_custom_log_level(level: str | int | None) -> None:
    global _custom_log_level
    if isinstance(level, int):
        level = logging.getLevelName(level)
    if level:
        _custom_log_level = level.upper()
    else:
        _custom_log_level = None


def get_config_dir() -> str:
    """Return the cross-platform configuration directory path."""
    if _custom_config_dir:
        return _custom_config_dir
    env_config_dir = os.getenv(f"{env_name}_CONFIG_DIR")
    if env_config_dir:
        return env_config_dir
    return str(user_config_dir(package_name))


def get_config_path() -> str:
    """Return the full, platform-specific path to the configuration file."""
    return os.path.join(get_config_dir(), CONFIG_FILE_NAME)


def _read_raw_config() -> Dict[str, Any]:
    """Reads the JSON configuration file without applying defaults or overrides."""
    from typing import cast

    config_path = get_config_path()
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    raise ConfigurationError(
                        "Startup configuration must be a JSON object."
                    )
                return cast(Dict[str, Any], data)
        except (json.JSONDecodeError, OSError) as e:
            log_operation_error(
                logger,
                "Failed to load configuration file at %s: %s",
                config_path,
                e,
                error=e,
            )
    return {}


def _resolve_setting(
    name: str,
    cli_val: Any,
    env_var_name: str,
    config: Dict[str, Any],
    config_key: str,
    default_val: Any,
) -> Any:
    """
    Resolves a setting in the order of precedence:
    1. CLI Argument
    2. Environment Variable
    3. Configuration File
    4. Default Value
    """
    if cli_val:
        logger.debug("Configuration '%s' supplied by command line.", name)
        return cli_val

    env_val = os.getenv(env_var_name)
    if env_val:
        logger.debug(
            "Configuration '%s' supplied by environment variable '%s'.",
            name,
            env_var_name,
        )
        return env_val

    if config_key in config and config[config_key]:
        return config[config_key]

    logger.debug("Configuration '%s' using its default.", name)
    return default_val


def load_config() -> Dict[str, Any]:
    """Resolve bootstrap values from CLI, environment, file and defaults, in that order."""
    config = _read_raw_config()
    final_config = config.copy()

    config_dir = get_config_dir()
    os.makedirs(config_dir, exist_ok=True)

    final_config["data_dir"] = _resolve_setting(
        name="data_dir",
        cli_val=_custom_data_dir,
        env_var_name=f"{env_name}_DATA_DIR",
        config=config,
        config_key="data_dir",
        default_val=os.path.join(config_dir, "data"),
    )

    final_config["db_url"] = _resolve_setting(
        name="db_url",
        cli_val=_custom_db_url,
        env_var_name=f"{env_name}_DB_URL",
        config=config,
        config_key="db_url",
        default_val=f"sqlite:///{os.path.join(config_dir, f'{package_name}.db')}",
    )

    final_log_level = _resolve_setting(
        name="log_level",
        cli_val=_custom_log_level,
        env_var_name=f"{env_name}_LOG_LEVEL",
        config=config,
        config_key="logging_level",
        default_val="INFO",
    )
    if isinstance(final_log_level, str):
        final_log_level = final_log_level.upper()
    final_config["logging_level"] = final_log_level

    try:
        return BootstrapConfig.model_validate(final_config).model_dump(mode="json")
    except ValidationError as error:
        raise ConfigurationError("Invalid startup configuration.") from error


def save_config(data: Dict[str, Any]):
    """Save the given data to the JSON configuration file.

    It ensures the configuration directory exists and writes the data with an indent
    for readability.

    :param data: The configuration data to save.
    """
    # Validate the raw file independently of CLI/environment overrides. Keep
    # absent fields absent so saving never freezes resolved default values.
    try:
        validated = BootstrapConfig.model_validate(
            {"data_dir": ".", "db_url": "sqlite://", **data}
        )
        raw = validated.model_dump(mode="json", include=set(data))
        encoded = json.dumps(raw, indent=4, allow_nan=False)
    except (ValidationError, ValueError, TypeError) as error:
        raise ConfigurationError("Invalid startup configuration.") from error
    temporary = None
    with _config_write_lock:
        try:
            os.makedirs(get_config_dir(), exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=get_config_dir(),
                prefix=".bsm-config-",
                delete=False,
            ) as file:
                temporary = file.name
                file.write(encoded)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, get_config_path())
        except OSError as error:
            log_operation_error(
                logger,
                "Failed to save configuration file at %s",
                get_config_path(),
                error=error,
            )
            raise ConfigurationError("Could not save startup configuration.") from error
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)


def get_config_value(key: str, default: Any = None) -> Any:
    """Read a dotted bootstrap key, returning the default when it is absent."""
    config = load_config()
    keys = key.split(".")
    value = config
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return default
    return value


def set_config_value(key: str, value: Any):
    """Persist one bootstrap key while preserving other explicit file values."""
    with _config_write_lock:
        config = _read_raw_config()
        parts = key.split(".")
        if not all(parts):
            raise ConfigurationError("Configuration key cannot be empty.")
        current = config
        for part in parts[:-1]:
            child = current.setdefault(part, {})
            if not isinstance(child, dict):
                raise ConfigurationError(
                    "Configuration path conflicts with an existing value."
                )
            current = child
        current[parts[-1]] = value
        save_config(config)
