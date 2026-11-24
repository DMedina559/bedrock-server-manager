"""Serializable install and update API request and response contracts."""

from ...models.install import (
    InstallNewServerRequest,
    InstallNewServerResponse,
    InstallServerPayload,
    UpdateServerRequest,
    UpdateServerResponse,
)

__all__ = [
    "InstallNewServerRequest",
    "InstallNewServerResponse",
    "InstallServerPayload",
    "UpdateServerRequest",
    "UpdateServerResponse",
]
