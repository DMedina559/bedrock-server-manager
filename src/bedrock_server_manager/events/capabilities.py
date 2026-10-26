"""Scoped event capabilities capture their bus lifetime, never AppContext."""

import inspect
import re
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable

from pydantic import BaseModel

from .bus import EventBus, _callback_identity


def create_event_capabilities(
    plugin_name: str, bus: EventBus | None, *, is_core: bool = False
) -> tuple[Callable[..., Any], Callable[..., Any], Callable[..., Any]]:
    event_owner = "application" if is_core else f"plugin:{plugin_name}"
    event_generation = bus.owner_generation(event_owner) if bus else 0

    def require_event_owner():
        if bus is None:
            raise RuntimeError("Event bus is unavailable")
        bus.check_owner(event_owner, event_generation)

    def normalize_options(options: dict[str, Any]) -> dict[str, Any]:
        options = dict(options)

        def normalize_identifier(value: Any) -> str:
            if not isinstance(value, str):
                raise TypeError("Listener IDs and ordering references must be strings")
            if not value or not re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_.:-]*", value):
                raise ValueError(
                    "Listener IDs and ordering references must be nonempty identifiers"
                )
            normalized: str = value if ":" in value else f"{plugin_name}:{value}"
            namespace, _, suffix = normalized.partition(":")
            if not namespace or not suffix or len(normalized) > 160:
                raise ValueError(
                    "Listener identifiers require a namespace and name within 160 characters"
                )
            return normalized

        identifier = options.get("listener_id")
        if identifier is not None:
            identifier = normalize_identifier(identifier)
            if not is_core and not identifier.startswith(f"{plugin_name}:"):
                raise ValueError("Listener IDs must use the plugin namespace")
            options["listener_id"] = identifier
        for key in ("before", "after"):
            values = options.get(key, ())
            if isinstance(values, (str, bytes)) or values is None:
                raise TypeError(
                    "Ordering references must be a sequence of listener IDs"
                )
            options[key] = tuple(normalize_identifier(value) for value in values)
        return options

    def typed_listener(
        name: str,
        callback: Callable[..., Any],
        *,
        observer: bool = False,
        payload_model: type[BaseModel] | None = None,
        **options: Any,
    ):
        require_event_owner()
        if bus is None:
            raise RuntimeError("Event bus is unavailable")
        if not callable(callback):
            raise TypeError("Event listener must be callable")
        definition = bus.registry.definition(name) if name != "*" else None
        if (
            definition is not None
            and bus.registry.declared(name)
            and not (
                is_core
                or definition.public
                or definition.owner == event_owner
                or (
                    definition.owner == "application"
                    and definition.phase == "lifecycle"
                )
            )
        ):
            raise PermissionError("Event contract is private to another plugin")
        if payload_model is not None and (
            not isinstance(payload_model, type)
            or not issubclass(payload_model, BaseModel)
        ):
            raise TypeError("Typed handlers require a Pydantic payload model")
        if inspect.iscoroutinefunction(callback):

            @wraps(callback)
            async def wrapped(*_args: Any, **_data: Any):
                await callback(bus.handler(payload_model))

        else:

            @wraps(callback)
            def wrapped(*_args: Any, **_data: Any):
                result = callback(bus.handler(payload_model))
                if inspect.isawaitable(result):

                    async def discard():
                        await result

                    return discard()
                return None

        return event_listener(
            name,
            wrapped,
            observer=observer,
            kind="observer" if observer else "hook",
            callback_identity=(*_callback_identity(callback), id(payload_model)),
            **options,
        )

    @contextmanager
    def operation_scope(name: str, *, server_name: str | None = None):
        require_event_owner()
        if bus is None:
            raise RuntimeError("Event bus is unavailable")
        if (
            not isinstance(name, str)
            or not name.startswith(f"{plugin_name}:")
            or len(name) <= len(plugin_name) + 1
            or len(name) > 160
        ):
            raise ValueError("Plugin operations must use the plugin namespace")
        from ..operations import operation_source

        with (
            operation_source(event_owner),
            bus.operations.scope(name, server_name=server_name) as operation,
        ):
            yield operation.snapshot

    def event_listener(
        event_name: str,
        callback: Callable[..., Any],
        *,
        once: bool = False,
        priority: int = 0,
        **options: Any,
    ):
        require_event_owner()
        if bus is None:
            raise RuntimeError("Event bus is unavailable")
        return bus.subscribe(
            event_name,
            callback,
            owner=event_owner,
            active=is_core,
            generation=event_generation,
            once=once,
            priority=priority,
            **normalize_options(options),
        )

    async def event_sender(event_name: str, *args: Any, **kwargs: Any):
        require_event_owner()
        if bus is None:
            raise RuntimeError("Event bus is unavailable")
        kwargs["_triggering_plugin"] = plugin_name
        definition = bus.registry.definition(event_name)
        if not is_core and (
            not bus.registry.declared(event_name)
            or definition.phase != "custom"
            or definition.owner != event_owner
        ):
            raise ValueError("Plugins may only emit their own declared custom events")
        return await bus.emit(event_name, kwargs, *args, source=event_owner)

    def event_dispatcher(action: str, *args: Any, **kwargs: Any):
        if action == "cleanup_subscription":
            if bus is not None:
                bus.release_subscription(args[0], owner=event_owner)
            return None
        require_event_owner()
        if bus is None:
            raise RuntimeError("Event bus is unavailable")
        if action == "current":
            return bus.event_context()
        if action == "handler":
            return bus.handler(*args, **kwargs)
        if action == "hook":
            return typed_listener(*args, **kwargs)
        if action == "subscription":
            mode = kwargs.pop("mode")
            if mode == "legacy":
                return event_listener(*args, temporary=True, **kwargs)
            return typed_listener(
                *args, observer=mode == "observer", temporary=True, **kwargs
            )
        if action == "observe":
            return typed_listener(*args, observer=True, **kwargs)
        if action == "catalog":
            from .models import EventCatalog

            return EventCatalog(
                events=[
                    definition
                    for definition in bus.registry.catalog().events
                    if is_core
                    or definition.public
                    or definition.owner == event_owner
                    or (
                        definition.owner == "application"
                        and definition.phase == "lifecycle"
                    )
                ]
            )
        if action == "describe":
            name = args[0]
            if not bus.registry.declared(name):
                raise KeyError(name)
            definition = bus.registry.definition(name)
            if not (
                is_core
                or definition.public
                or definition.owner == event_owner
                or (
                    definition.owner == "application"
                    and definition.phase == "lifecycle"
                )
            ):
                raise PermissionError("Event contract is private to another plugin")
            return definition
        if action == "subscriptions":
            return bus.subscriptions(event_owner)
        if action == "operation_scope":
            return operation_scope(*args, **kwargs)
        if action == "operation_activity":
            return bus.operations.activity(*args, **kwargs)
        if action == "operation_current":
            return bus.operations.current()
        if action == "operation_sequence":
            return bus.operations.sequence()
        if action == "operation_results":
            return bus.operations.results(*args, **kwargs)
        if action == "listen":
            return event_listener(*args, **kwargs)
        if action == "once":
            return event_listener(*args, once=True, **kwargs)
        if action == "wait_for":
            return bus.wait_for(
                *args,
                owner=event_owner,
                generation=event_generation,
                active=is_core,
                **kwargs,
            )
        if action == "emit":
            definition = bus.registry.definition(args[0])
            if not is_core and (
                not bus.registry.declared(args[0])
                or definition.phase != "custom"
                or definition.owner != event_owner
            ):
                raise ValueError(
                    "Plugins may only emit their own declared custom events"
                )
            return event_sender(*args, **kwargs)
        if action == "diagnostics":
            return bus.diagnostics(*args, **kwargs)
        if action == "unsubscribe":
            bus.unsubscribe(args[0], owner=event_owner)
            return None
        if action == "define":
            from .models import EventDefinition

            name, model = args
            if (
                not name.startswith(f"{plugin_name}:")
                or not isinstance(model, type)
                or not issubclass(model, BaseModel)
            ):
                raise ValueError(
                    "Declare a Pydantic payload under the plugin's namespace"
                )
            definition = EventDefinition(
                name=name,
                owner=event_owner,
                description=kwargs.get("description", ""),
                public=kwargs.get("public", True),
            )
            bus.define(definition, model, generation=event_generation)
            return bus.registry.definition(name)
        raise ValueError(f"Unknown event capability: {action}")

    return event_listener, event_sender, event_dispatcher
