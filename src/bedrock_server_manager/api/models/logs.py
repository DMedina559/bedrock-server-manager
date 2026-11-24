"""Serializable server log API contracts."""

from ...models.logs import WaitForServerLogRequest, WaitForServerLogResponse

__all__ = [
    "WaitForServerLogRequest",
    "WaitForServerLogResponse",
]
