"""Validate declared data contracts without importing application runtime state."""

import asyncio
import functools
import inspect
import logging
import time
from typing import Any, Callable, TypeVar, cast, get_type_hints

from pydantic import BaseModel, ValidationError

from ..error import APIResponseValidationError
from ..logging import log_operation_error
from ..utils.progress import report_stage

F = TypeVar("F", bound=Callable[..., Any])


_OPERATION_STAGES = {
    "start_server": "Preparing server start",
    "stop_server": "Stopping server",
    "restart_server": "Restarting server",
    "import_addon": "Installing add-on",
    "enable_addon": "Enabling add-on",
    "disable_addon": "Disabling add-on",
    "update_subpack": "Updating subpack",
    "uninstall_addon": "Removing add-on",
    "reorder_addons": "Updating add-on order",
    "install_new_server": "Installing server",
    "update_server": "Updating server",
    "delete_server_data": "Deleting server",
    "import_world": "Importing world",
    "export_world": "Exporting world",
    "reset_world": "Resetting world",
    "backup_all": "Preparing backup",
    "restore_all": "Preparing restore",
    "prune_old_backups": "Pruning backups",
    "backup_world": "Preparing world backup",
    "backup_config_file": "Backing up configuration",
    "restore_world": "Restoring world",
    "restore_config_file": "Restoring configuration",
    "create_server_backup": "Preparing backup",
    "restore_server_snapshot": "Preparing restore",
    "manage_server_snapshot": "Managing backup",
    "recover_server_backup": "Recovering interrupted restore",
    "dry_run_server_restore": "Checking restore",
    "cleanup_backup_destination": "Cleaning backup destination",
    "prepare_backup_copy": "Cloning server",
    "prune_download_cache": "Pruning downloads",
}


def get_contract(
    func: Callable[..., Any],
) -> tuple[type[BaseModel], type[BaseModel]] | None:
    """Legacy operations have no contract; partial new contracts are errors."""
    signature = inspect.signature(func)

    if "request" not in signature.parameters:
        annotation = signature.return_annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            raise TypeError(f"API {func.__name__} needs a request model")
        return None
    hints = get_type_hints(inspect.unwrap(func))
    request_type = hints.get("request")
    response_type = hints.get("return")
    if (
        not isinstance(request_type, type)
        or not issubclass(request_type, BaseModel)
        or not isinstance(response_type, type)
        or not issubclass(response_type, BaseModel)
    ):
        raise TypeError(
            f"API {func.__name__} needs request and response model annotations"
        )
    if set(signature.parameters) - {"request", "app_context", "plugin_name"}:
        raise TypeError(
            f"API {func.__name__} must take a single request plus runtime dependencies"
        )
    if signature.parameters["request"].default is not inspect.Parameter.empty:
        raise TypeError(f"API {func.__name__} requires an explicit request")
    if {"app_context", "plugin_name"} & request_type.model_fields.keys():
        raise TypeError(f"API {func.__name__} request contains runtime dependencies")
    # Fail registration early for models that cannot describe a JSON contract.
    request_type.model_json_schema(mode="validation")
    response_type.model_json_schema(mode="serialization")
    return request_type, response_type


def validate_contract(func: F) -> F:
    """Validate input before events/side effects and output before returning."""
    contract = get_contract(func)
    if contract is None:
        return func
    request_type, response_type = contract
    signature = inspect.signature(func)
    logger = logging.getLogger(func.__module__)

    def validate_response(result: Any) -> BaseModel:
        if getattr(func, "__validates_event_result__", False):
            return cast(BaseModel, result)
        try:
            return response_type.model_validate(result)
        except ValidationError as error:
            raise APIResponseValidationError(
                f"API {func.__name__} produced invalid output"
            ) from error

    def bind(args: tuple[Any, ...], kwargs: dict[str, Any]) -> inspect.BoundArguments:
        bound = signature.bind(*args, **kwargs)
        bound.arguments["request"] = request_type.model_validate(
            bound.arguments["request"]
        )
        return bound

    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> BaseModel:
            started = time.monotonic()
            logger.debug("API %s started", func.__name__)
            outcome = "completed"
            try:
                bound = bind(args, kwargs)
                if func.__name__ in _OPERATION_STAGES:
                    await report_stage(_OPERATION_STAGES[func.__name__])
                try:
                    result = await func(*bound.args, **bound.kwargs)
                except ValidationError as error:
                    raise APIResponseValidationError(
                        f"API {func.__name__} failed internal data validation"
                    ) from error
                return validate_response(result)
            except asyncio.CancelledError:
                outcome = "cancelled"
                logger.debug("API %s cancelled", func.__name__)
                raise
            except Exception as error:
                outcome = "failed"
                log_operation_error(logger, "API %s failed", func.__name__, error=error)
                raise
            finally:
                logger.debug(
                    "API %s finished: %s (%.3f ms)",
                    func.__name__,
                    outcome,
                    (time.monotonic() - started) * 1000,
                )

        return cast(F, async_wrapper)

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> BaseModel:
        started = time.monotonic()
        outcome = "completed"
        logger.debug("API %s started", func.__name__)
        try:
            bound = bind(args, kwargs)
            try:
                result = func(*bound.args, **bound.kwargs)
            except ValidationError as error:
                raise APIResponseValidationError(
                    f"API {func.__name__} failed internal data validation"
                ) from error
            return validate_response(result)
        except Exception as error:
            outcome = "failed"
            log_operation_error(logger, "API %s failed", func.__name__, error=error)
            raise
        finally:
            logger.debug(
                "API %s finished: %s (%.3f ms)",
                func.__name__,
                outcome,
                (time.monotonic() - started) * 1000,
            )

    return cast(F, sync_wrapper)
