"""Utility exports load only their requested implementation."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .general import get_timestamp as get_timestamp
    from .general import list_content_files as list_content_files
    from .server import (
        core_validate_server_name_format as core_validate_server_name_format,
    )
    from .server import get_servers_data as get_servers_data
    from .server import validate_server as validate_server

_EXPORTS = {
    "get_timestamp": "general",
    "list_content_files": "general",
    "core_validate_server_name_format": "server",
    "get_servers_data": "server",
    "validate_server": "server",
}


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(name)
    value = getattr(import_module("." + _EXPORTS[name], __name__), name)
    globals()[name] = value
    return value


__all__ = [
    "get_timestamp",
    "list_content_files",
    "core_validate_server_name_format",
    "get_servers_data",
    "validate_server",
]
