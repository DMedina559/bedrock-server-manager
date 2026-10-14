"""Public background task contracts; execution handles remain in TaskManager."""

from typing import Literal, Self

from pydantic import JsonValue, model_validator

from .common import APIErrorResponse, APIResponse, StateRevision


class TaskAcceptedResponse(APIResponse):
    status: Literal["accepted"] = "accepted"
    message: str
    task_id: str


class TaskState(APIResponse):
    status: Literal[
        "queued", "running", "completed", "failed", "cancelling", "cancelled"
    ]
    message: str
    result: JsonValue = None
    error: APIErrorResponse | None = None

    @model_validator(mode="after")
    def coherent_task(self) -> Self:
        if self.status == "completed" and self.error is not None:
            raise ValueError("Completed tasks cannot contain errors.")
        if self.status == "failed" and self.error is None:
            raise ValueError("Failed tasks require an error.")
        if self.status != "completed" and self.result is not None:
            raise ValueError("Only completed tasks may contain results.")
        if self.status not in {"failed", "cancelled"} and self.error is not None:
            raise ValueError("Active tasks cannot contain errors.")
        if (
            self.status == "cancelled"
            and self.error is not None
            and self.error.code != "operation_canceled"
        ):
            raise ValueError("Cancelled tasks may only contain cancellation errors.")
        return self


class TaskSnapshot(TaskState, StateRevision):
    id: str
