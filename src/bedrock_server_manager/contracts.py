"""Transport-independent validated data shared by application layers."""

from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    SecretStr,
    TypeAdapter,
    model_validator,
)

NonEmptyStr = Annotated[str, Field(strict=True, min_length=1, pattern=r".*\S.*")]
ServerName = Annotated[
    str,
    Field(strict=True, min_length=1, pattern=r"^[a-zA-Z0-9_-]+$", examples=["example"]),
]


def validate_password_size(value: SecretStr) -> SecretStr:
    if len(value.get_secret_value().encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 UTF-8 bytes.")
    return value


Password = Annotated[
    SecretStr, Field(min_length=1), AfterValidator(validate_password_size)
]


class DataContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        hide_input_in_errors=True,
        strict=True,
        frozen=True,
        revalidate_instances="always",
        validate_default=True,
        allow_inf_nan=False,
    )


class FailureInfo(DataContract):
    code: Literal[
        "validation_error",
        "not_found",
        "conflict",
        "forbidden",
        "unauthorized",
        "http_error",
        "operation_canceled",
        "invalid_server_name",
        "server_start_failed",
        "server_stop_failed",
        "server_error",
        "application_error",
        "internal_error",
        "unavailable",
        "operation_incomplete",
        "file_error",
        "storage_error",
        "configuration_error",
        "network_error",
        "system_error",
    ]
    message: str
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ClassifiedFailure(DataContract):
    error: FailureInfo
    status_code: int = Field(ge=400, le=599)
    expected: bool


class CompletedItem(DataContract):
    outcome: Literal["completed"] = "completed"
    path: str | None = None
    reason: None = None
    error: None = None


class SkippedItem(DataContract):
    outcome: Literal["skipped"] = "skipped"
    path: None = None
    reason: str
    error: None = None


class FailedItem(DataContract):
    outcome: Literal["failed"] = "failed"
    path: None = None
    reason: str | None = None
    error: FailureInfo


ItemResult = Annotated[
    CompletedItem | SkippedItem | FailedItem, Field(discriminator="outcome")
]
_ITEM: TypeAdapter[ItemResult] = TypeAdapter(ItemResult)


class ComponentResults(DataContract):
    components: dict[str, ItemResult] = Field(default_factory=dict)

    outcome: Literal["completed", "partial", "failed", "noop"] = "noop"

    @model_validator(mode="before")
    @classmethod
    def derive_outcome(cls, data: object) -> object:
        if isinstance(data, dict):
            data = dict(data)
            raw_items = data.get("components", {})
            if not isinstance(raw_items, dict):
                return data
            items = {
                key: _ITEM.validate_python(value) for key, value in raw_items.items()
            }
            data["components"] = items
            completed = any(item.outcome == "completed" for item in items.values())
            failed = any(item.outcome == "failed" for item in items.values())
            expected = (
                "partial"
                if completed and failed
                else "failed" if failed else "completed" if completed else "noop"
            )
            if "outcome" in data and data["outcome"] != expected:
                raise ValueError("Aggregate outcome must match its components.")
            data["outcome"] = expected
        return data

    @model_validator(mode="after")
    def coherent_outcome(self) -> Self:
        completed = any(
            item.outcome == "completed" for item in self.components.values()
        )
        failed = any(item.outcome == "failed" for item in self.components.values())
        expected = (
            "partial"
            if completed and failed
            else "failed" if failed else "completed" if completed else "noop"
        )
        if self.outcome != expected:
            raise ValueError("Aggregate outcome must match its components.")
        return self


class CleanupResult(DataContract):
    deleted: list[str] = Field(default_factory=list)
    retained: list[str] = Field(default_factory=list)
    failures: dict[str, FailureInfo] = Field(default_factory=dict)

    outcome: Literal["completed", "partial", "failed", "noop"] = "noop"

    @model_validator(mode="before")
    @classmethod
    def derive_outcome(cls, data: object) -> object:
        if isinstance(data, dict):
            data = dict(data)
            failures, deleted = data.get("failures", {}), data.get("deleted", [])
            expected = (
                "partial"
                if failures and deleted
                else "failed" if failures else "completed" if deleted else "noop"
            )
            if "outcome" in data and data["outcome"] != expected:
                raise ValueError("Cleanup outcome must match its items.")
            data["outcome"] = expected
        return data

    @model_validator(mode="after")
    def coherent_outcome(self) -> Self:
        expected = (
            "partial"
            if self.failures and self.deleted
            else "failed" if self.failures else "completed" if self.deleted else "noop"
        )
        if self.outcome != expected:
            raise ValueError("Cleanup outcome must match its items.")
        if set(self.deleted) & (set(self.retained) | self.failures.keys()):
            raise ValueError("Deleted paths cannot also be retained or failed.")
        return self


class DeliveryResult(DataContract):
    targeted: int = Field(default=0, ge=0)
    sent: int = Field(default=0, ge=0)
    unavailable: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def coherent_counts(self) -> Self:
        if self.targeted != self.sent + self.unavailable + self.failed:
            raise ValueError("Every targeted recipient must have an outcome.")
        return self

    @classmethod
    def combine(cls, items: list["DeliveryResult"]) -> "DeliveryResult":
        return cls(
            **{
                key: sum(getattr(item, key) for item in items)
                for key in cls.model_fields
            }
        )


class BanMutation(DataContract):
    outcome: Literal["added", "updated", "removed"]
    message: str


class ResourceFailure(DataContract):
    resource: str
    error: FailureInfo


class PlayerScanError(DataContract):
    server: str
    error: FailureInfo


class PlayerScanDetails(DataContract):
    total_entries_in_logs: int = Field(ge=0)
    unique_players_submitted_for_saving: int = Field(ge=0)
    actually_saved_or_updated_in_db: int = Field(ge=0)
    scan_errors: list[PlayerScanError] = Field(default_factory=list)

    @model_validator(mode="after")
    def coherent_counts(self) -> Self:
        if not (
            self.actually_saved_or_updated_in_db
            <= self.unique_players_submitted_for_saving
            <= self.total_entries_in_logs
        ):
            raise ValueError("Saved, unique, and discovered counts must be coherent.")
        return self


class CommittedMutationResult(DataContract):
    committed: Literal[True] = True
    action: str
    resource: str
    recovery_error: FailureInfo
