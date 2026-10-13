"""Utility exports load only their requested implementation."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .auth import authenticate_user as authenticate_user
    from .auth import authenticate_websocket_token as authenticate_websocket_token
    from .auth import create_access_token as create_access_token
    from .auth import get_jwt_secret_key as get_jwt_secret_key
    from .auth import get_password_hash as get_password_hash
    from .auth import verify_password as verify_password
    from .general import get_timestamp as get_timestamp
    from .general import list_content_files as list_content_files
    from .get_utils import get_operating_system_type as get_operating_system_type
    from .server import (
        core_validate_server_name_format as core_validate_server_name_format,
    )
    from .server import get_servers_data as get_servers_data
    from .server import validate_server as validate_server

_EXPORTS = {
    "authenticate_user": "auth",
    "authenticate_websocket_token": "auth",
    "create_access_token": "auth",
    "get_jwt_secret_key": "auth",
    "get_password_hash": "auth",
    "verify_password": "auth",
    "get_timestamp": "general",
    "list_content_files": "general",
    "get_operating_system_type": "get_utils",
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
    "authenticate_user",
    "authenticate_websocket_token",
    "create_access_token",
    "get_jwt_secret_key",
    "get_password_hash",
    "verify_password",
    "get_timestamp",
    "list_content_files",
    "get_operating_system_type",
    "core_validate_server_name_format",
    "get_servers_data",
    "validate_server",
]
