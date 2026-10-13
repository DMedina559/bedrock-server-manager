"""Operation hooks with typed payloads, independent of API registration."""

import functools
import inspect
from copy import deepcopy
from typing import (
    Any,
    Awaitable,
    Callable,
    ParamSpec,
    TypeVar,
    cast,
    get_type_hints,
    overload,
)

from pydantic import BaseModel, ConfigDict, ValidationError, create_model

from ..error import APICancelledError, APIResponseValidationError
from ..state_revision import revision_clock
from .bus import correlation_scope
from .control import CancellableEvent
from .models import EventDefinition
from .registry import builtin_events

P = ParamSpec("P")
R = TypeVar("R")


@overload
def trigger_event(_func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]: ...


@overload
def trigger_event(
    _func: None = None,
    *,
    before: str | None = None,
    after: str | None = None,
    identity_keys: tuple[str, ...] | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]: ...


def trigger_event(
    _func: Callable[P, Awaitable[R]] | None = None,
    *,
    before: str | None = None,
    after: str | None = None,
    identity_keys: tuple[str, ...] | None = None,
) -> (
    Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]
    | Callable[P, Awaitable[R]]
):
    def decorate(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        signature = inspect.signature(func)
        hints = get_type_hints(func)
        request_type, response_type = hints.get("request"), hints.get("return")
        typed_response = isinstance(response_type, type) and issubclass(
            response_type, BaseModel
        )
        declarations = []
        for name, phase in ((before, "before"), (after, "after")):
            if name is None:
                continue
            fields: dict[str, Any] = {}
            if isinstance(request_type, type) and issubclass(request_type, BaseModel):
                fields["request"] = (request_type, ...)
                for key, field in request_type.model_fields.items():
                    if field.exclude:
                        continue
                    key = "plugin_name" if key == "target_plugin_name" else key
                    fields[key] = (field.annotation, deepcopy(field))
            if phase == "after" and typed_response:
                fields["result"] = (response_type, ...)
            model = (
                create_model(
                    f"{name}_{func.__name__}_payload",
                    __config__=ConfigDict(extra="allow"),
                    **fields,
                )
                if fields
                else None
            )
            declarations.append(
                (
                    EventDefinition(
                        name=name,
                        phase=phase,
                        description=(
                            f"Triggered {phase} '{func.__name__}'. "
                            + (inspect.getdoc(func) or "No description.").splitlines()[
                                0
                            ]
                        ),
                        identity_keys=identity_keys or (),
                        payload_schema=(
                            model.model_json_schema(mode="serialization")
                            if model
                            else {}
                        ),
                    ),
                    model,
                )
            )
            if func.__module__.startswith("bedrock_server_manager."):
                builtin_events.register(*declarations[-1], allow_variants=True)

        @functools.wraps(func)
        async def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            with correlation_scope():
                bound = signature.bind(*args, **kwargs)
                bound.apply_defaults()
                if isinstance(request_type, type) and issubclass(
                    request_type, BaseModel
                ):
                    bound.arguments["request"] = request_type.model_validate(
                        bound.arguments["request"]
                    )
                data = dict(bound.arguments)
                context = data.get("app_context")
                if context is not None and not func.__module__.startswith(
                    "bedrock_server_manager."
                ):
                    for declaration, model in declarations:
                        context.events.registry.register(declaration, model)
                request = data.get("request")
                if isinstance(request, BaseModel):
                    request = deepcopy(request)
                    data["request"] = request
                    data.update(
                        {
                            key: getattr(request, key)
                            for key, field in type(request).model_fields.items()
                            if not field.exclude
                        }
                    )
                    if "target_plugin_name" in data:
                        data["plugin_name"] = data.pop("target_plugin_name")
                control = CancellableEvent()
                data["event"] = control
                if before and context is not None:
                    try:
                        await context.events.emit(
                            before, data, revision=dict(revision_clock.capture())
                        )
                    finally:
                        control.seal()
                    if control.is_cancelled:
                        if "request" in signature.parameters:
                            raise APICancelledError(
                                control.cancel_reason or "Cancelled by plugin"
                            )
                        return cast(
                            R,
                            {
                                "status": "canceled",
                                "message": control.cancel_reason
                                or "Cancelled by plugin",
                            },
                        )
                else:
                    control.seal()
                result = await func(*bound.args, **bound.kwargs)
                if typed_response and response_type is not None:
                    try:
                        result = response_type.model_validate(result)
                    except ValidationError as error:
                        raise APIResponseValidationError(
                            f"Operation {func.__name__} produced invalid output"
                        ) from error
                if after and context is not None:
                    data["result"] = deepcopy(result)
                    await context.events.emit(
                        after, data, revision=dict(revision_clock.capture())
                    )
                return cast(R, result)

        setattr(wrapped, "__validates_event_result__", typed_response)
        return wrapped

    return decorate(_func) if _func is not None else decorate
