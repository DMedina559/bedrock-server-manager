"""Partial domain updates distinguish omission from explicit null."""

from enum import Enum

from pydantic import JsonValue

from .models import PersistentRecord


class Unset(Enum):
    VALUE = "unset"


UNSET = Unset.VALUE


class ServerUpdate(PersistentRecord):
    server_name: str
    installed_version: str | None = None
    status: str | None = None
    autoupdate: bool | None = None
    autostart: bool | None = None
    target_version: str | None = None
    custom: dict[str, JsonValue] | None = None


class UserUpdate(PersistentRecord):
    username: str
    role: str | None = None
    theme: str | None = None
    is_active: bool | None = None
    full_name: str | None = None
    email: str | None = None
    id: int | None = None


class PluginUpdate(PersistentRecord):
    plugin_name: str
    enabled: bool | None = None
    version: str | None = None
    author: str | None = None
    description: str | None = None
