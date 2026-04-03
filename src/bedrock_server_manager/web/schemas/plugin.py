from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .base import BaseApiResponse


class PluginStatusSetPayload(BaseModel):
    """Request model for setting a plugin's enabled status."""

    enabled: bool = Field(
        ..., description="Set to true to enable the plugin, false to disable."
    )


class TriggerEventPayload(BaseModel):
    """Request model for triggering a custom plugin event."""

    event_name: str = Field(
        ...,
        min_length=1,
        description="The namespaced name of the event to trigger (e.g., 'myplugin:myevent').",
    )
    payload: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional dictionary payload for the event."
    )


class PluginPagesResponse(BaseApiResponse):
    """Response model for plugin native UI pages."""

    pages: Optional[List[Dict[str, Any]]] = None


class PluginStatusesResponse(BaseApiResponse):
    """Response model for plugin statuses."""

    plugins: Optional[Dict[str, Dict[str, Any]]] = None


class TriggerEventResponse(BaseApiResponse):
    """Response model for triggering a custom plugin event."""

    details: Optional[Dict[str, Any]] = None
