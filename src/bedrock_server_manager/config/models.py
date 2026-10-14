"""Validated startup configuration after CLI/environment/file precedence."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator
from sqlalchemy.engine import make_url


class BootstrapConfig(BaseModel):
    # Extension settings (CORS, integrations, etc.) are retained as JSON.
    model_config = ConfigDict(
        extra="allow", strict=True, validate_default=True, allow_inf_nan=False
    )
    __pydantic_extra__: dict[str, JsonValue] = Field(init=False)

    data_dir: Annotated[str, Field(min_length=1)]
    db_url: Annotated[str, Field(min_length=1)]
    logging_level: Literal[
        "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NOTSET"
    ] = "INFO"

    @field_validator("db_url")
    @classmethod
    def validate_db_url(cls, value: str) -> str:
        try:
            make_url(value)
        except Exception as error:
            raise ValueError("Invalid database URL") from error
        return value

    @field_validator("logging_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.upper()
            return {"WARN": "WARNING", "FATAL": "CRITICAL"}.get(value, value)
        return value
