"""Validate declared data contracts without importing application runtime state."""

import functools
import inspect
from typing import Any, Callable, TypeVar, cast, get_type_hints

from pydantic import BaseModel, ValidationError

F = TypeVar("F", bound=Callable[..., Any])


class APIResponseValidationError(RuntimeError):
    """A declared API produced invalid output; never classify as bad input."""


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

    def validate_response(result: Any) -> BaseModel:
        if getattr(func, "__validates_api_response__", False):
            return cast(BaseModel, result)
        try:
            return response_type.model_validate(result)
        except ValidationError as error:
            raise APIResponseValidationError(
                f"API {func.__name__} produced invalid output"
            ) from error

    def bind(args: tuple[Any, ...], kwargs: dict[str, Any]):
        bound = signature.bind(*args, **kwargs)
        bound.arguments["request"] = request_type.model_validate(
            bound.arguments["request"]
        )
        return bound

    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> BaseModel:
            bound = bind(args, kwargs)
            try:
                result = await func(*bound.args, **bound.kwargs)
            except ValidationError as error:
                raise APIResponseValidationError(
                    f"API {func.__name__} failed internal data validation"
                ) from error
            return validate_response(result)

        return cast(F, async_wrapper)

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> BaseModel:
        bound = bind(args, kwargs)
        try:
            result = func(*bound.args, **bound.kwargs)
        except ValidationError as error:
            raise APIResponseValidationError(
                f"API {func.__name__} failed internal data validation"
            ) from error
        return validate_response(result)

    return cast(F, sync_wrapper)
