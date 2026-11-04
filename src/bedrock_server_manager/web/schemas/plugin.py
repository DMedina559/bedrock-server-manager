from typing import Dict, List, Optional

from pydantic import JsonValue

from ...models.plugins import PluginStatusSetPayload, TriggerEventPayload
from .base import BaseApiResponse


class PluginPagesResponse(BaseApiResponse):
    """Response model for plugin native UI pages."""

    pages: Optional[List[Dict[str, JsonValue]]] = None


__all__ = [
    "PluginPagesResponse",
    "PluginStatusSetPayload",
    "TriggerEventPayload",
]
