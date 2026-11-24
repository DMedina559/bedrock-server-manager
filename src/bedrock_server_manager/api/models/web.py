"""Serializable web API request and response contracts."""

from ...models.web import (
    CreateWebUiServiceRequest,
    CreateWebUiServiceResponse,
    DisableWebUiServiceRequest,
    DisableWebUiServiceResponse,
    EnableWebUiServiceRequest,
    EnableWebUiServiceResponse,
    GetWebUiServiceStatusRequest,
    GetWebUiServiceStatusResponse,
    RemoveWebUiServiceRequest,
    RemoveWebUiServiceResponse,
)

__all__ = [
    "CreateWebUiServiceRequest",
    "CreateWebUiServiceResponse",
    "DisableWebUiServiceRequest",
    "DisableWebUiServiceResponse",
    "EnableWebUiServiceRequest",
    "EnableWebUiServiceResponse",
    "GetWebUiServiceStatusRequest",
    "GetWebUiServiceStatusResponse",
    "RemoveWebUiServiceRequest",
    "RemoveWebUiServiceResponse",
]
