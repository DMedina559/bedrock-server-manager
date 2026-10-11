"""Reusable Pydantic types for settings validated against live application state."""

from typing import Annotated

from pydantic import AfterValidator, Field, ValidationInfo


def _existing_server(value: str, info: ValidationInfo) -> str:
    if info.context is not None and value not in info.context["server_names"]:
        raise ValueError("Select an existing server.")
    return value


ExistingServerName = Annotated[
    str,
    Field(
        strict=True,
        min_length=1,
        pattern=r"^[a-zA-Z0-9_-]+$",
        json_schema_extra={"x-bsm-server-name": True},
    ),
    AfterValidator(_existing_server),
]
