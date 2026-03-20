from typing import Any, Dict, Optional

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


class PluginApiResponse(BaseApiResponse):
    """Generic API response model for plugin operations."""

    # status: str -> Inherited
    # message: Optional[str] = None -> Inherited
    data: Optional[Any] = Field(
        default=None,
        description="Optional data payload, structure depends on the endpoint (e.g., plugin statuses).",
    )
