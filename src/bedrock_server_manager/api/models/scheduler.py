"""Serializable scheduler configuration and bounded run metadata."""

from typing import Literal

from pydantic import Field, JsonValue, field_validator

from ...state.settings import ScheduledTask
from .common import APIRequest, APIResponse


class ScheduleConfigurationView(ScheduledTask):
    """Read saved definitions even if this host has lost their timezone data."""

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value):
        return value


class ScheduleEntry(APIResponse):
    schedule_id: str
    configuration: ScheduleConfigurationView
    available: bool
    legacy: bool = False
    next_run_at: str | None = None
    revision: str | None = None
    next_attempt_at: str | None = None
    retry_exhausted: bool = False
    blocked_reason: str | None = None
    last_evaluated_at: str | None = None
    last_status: str | None = None
    last_success_at: str | None = None
    last_error: str | None = None
    attempts: int = 0
    runs: list[dict[str, JsonValue]] = Field(default_factory=list)


class ListSchedulesRequest(APIRequest):
    server_name: str | None = None


class ListSchedulesResponse(APIResponse):
    server_time: str | None = None
    host_timezone: str | None = None
    timezone_database_available: bool = True
    timezones: list[str] = Field(default_factory=list)
    schedules: list[ScheduleEntry] = Field(default_factory=list)
    task_types: list[str] = Field(default_factory=list)
    task_definitions: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)


class SaveScheduleRequest(APIRequest):
    schedule_id: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,100}$")
    configuration: ScheduledTask


class DeleteScheduleRequest(APIRequest):
    schedule_id: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,100}$")


class ControlScheduleRequest(APIRequest):
    schedule_id: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,100}$")
    action: Literal["run_now", "pause", "resume", "retry"]
    revision: str | None = None


class ControlSchedulePayload(APIRequest):
    action: Literal["run_now", "pause", "resume", "retry"]
    revision: str | None = None
