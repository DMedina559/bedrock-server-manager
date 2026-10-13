"""Scoped event capabilities capture their bus lifetime, never AppContext."""

from typing import Any, Callable

from pydantic import BaseModel

from .bus import EventBus


def create_event_capabilities(
    plugin_name: str, bus: EventBus | None, *, is_core: bool = False
) -> tuple[Callable[..., Any], Callable[..., Any], Callable[..., Any]]:
    event_owner = "application" if is_core else f"plugin:{plugin_name}"
    event_generation = bus.owner_generation(event_owner) if bus else 0

    def require_event_owner():
        if bus is None:
            raise RuntimeError("Event bus is unavailable")
        bus.check_owner(event_owner, event_generation)

    def event_listener(
        event_name: str, callback: Callable[..., None], *, once: bool = False
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
        )

    async def event_sender(event_name: str, *args: Any, **kwargs: Any):
        require_event_owner()
        if bus is None:
            raise RuntimeError("Event bus is unavailable")
        kwargs["_triggering_plugin"] = plugin_name
        definition = bus.registry.definition(event_name)
        if (
            not is_core
            and bus.registry.declared(event_name)
            and (definition.phase != "custom" or definition.owner != event_owner)
        ):
            raise ValueError("Plugins may only emit their own declared custom events")
        return await bus.emit(event_name, kwargs, *args, source=event_owner)

    def event_dispatcher(action: str, *args: Any, **kwargs: Any):
        require_event_owner()
        if bus is None:
            raise RuntimeError("Event bus is unavailable")
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
