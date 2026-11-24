"""Generation-scoped live output waits; independent of lifecycle responses."""

from typing import Annotated

from pydantic import Field

from .common import APIRequest, ServerName, SuccessResponse


class WaitForServerLogRequest(APIRequest):
    server_name: ServerName
    text: Annotated[str, Field(min_length=1, max_length=4096)]
    generation: str | None = None
    exact: bool = False
    after_sequence: Annotated[int, Field(ge=0)] | None = None
    timeout: Annotated[float, Field(gt=0, le=300)] = 30


class WaitForServerLogResponse(SuccessResponse):
    server_name: ServerName
    generation: str
    sequence: int
    line: str
