"""Validated task data; execution futures remain owned by TaskManager."""

from typing import Any

from ..api.models.common import StateRevision
from ..api.models.tasks import TaskState


class TaskRecord(TaskState, StateRevision):
    username: str | None = None

    def __getitem__(self, key: str) -> Any:
        """Preserve read access for existing task-manager consumers."""
        if key not in type(self).model_fields:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return self[key] if key in type(self).model_fields else default
