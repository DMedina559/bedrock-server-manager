"""Declarations are independent of plugin discovery and HTTP routing."""

from functools import reduce
from operator import or_
from threading import RLock
from typing import Any

from pydantic import BaseModel, TypeAdapter

from .models import EventCatalog, EventDefinition


class EventRegistry:
    def __init__(self, parent: "EventRegistry | None" = None):
        self.parent = parent
        self._definitions: dict[str, EventDefinition] = {}
        self._models: dict[str, list[type[BaseModel]]] = {}
        self._adapters: dict[str, TypeAdapter[Any]] = {}
        self._lock = RLock()

    def register(
        self,
        definition: EventDefinition,
        payload_model: type[BaseModel] | None = None,
        *,
        allow_variants: bool = False,
    ) -> None:
        with self._lock:
            existing = self._definitions.get(definition.name)
            inherited = (
                existing is None
                and self.parent is not None
                and self.parent.declared(definition.name)
            )
            if inherited and self.parent is not None:
                existing = self.parent.definition(definition.name)
            if existing is not None and any(
                getattr(existing, field) != getattr(definition, field)
                for field in ("owner", "phase", "identity_keys", "public")
            ):
                raise ValueError(f"Conflicting event definition: {definition.name}")
            if inherited and self.parent is not None:
                if (
                    payload_model is not None
                    and payload_model not in self.parent.payload_models(definition.name)
                ):
                    raise ValueError("Inherited event contracts cannot be overridden")
                return
            models = list(self._models.get(definition.name, []))
            if payload_model is not None and payload_model not in models:
                if models and not allow_variants:
                    raise ValueError("Payload variants must be explicitly registered")
                models.append(payload_model)
            definition = definition.model_copy(deep=True)
            adapter = self._adapters.get(definition.name)
            if models and models != self._models.get(definition.name):
                adapter = TypeAdapter(reduce(or_, models))
            if adapter is not None:
                definition.payload_schema = adapter.json_schema(mode="serialization")
                self._adapters[definition.name] = adapter
            self._models[definition.name] = models
            self._definitions[definition.name] = definition

    def definition(self, name: str) -> EventDefinition:
        with self._lock:
            definition = self._definitions.get(name)
            if definition is None and self.parent is not None:
                return self.parent.definition(name)
            return (definition or EventDefinition(name=name)).model_copy(deep=True)

    def prepare(self, name: str, data: dict[str, Any]) -> Any:
        with self._lock:
            adapter = self._adapters.get(name)
            local = name in self._definitions
        if adapter is not None:
            return adapter.validate_python(data)
        if not local and self.parent is not None:
            return self.parent.prepare(name, data)
        return data

    def payload_models(self, name: str) -> tuple[type[BaseModel], ...]:
        """Read payload model variants for contract tools and documentation."""
        with self._lock:
            if name in self._models:
                return tuple(self._models[name])
            return self.parent.payload_models(name) if self.parent else ()

    def declared(self, name: str) -> bool:
        with self._lock:
            return name in self._definitions or (
                self.parent is not None and self.parent.declared(name)
            )

    def remove_owner(self, owner: str) -> None:
        with self._lock:
            for name, definition in list(self._definitions.items()):
                if definition.owner == owner:
                    self._definitions.pop(name)
                    self._models.pop(name, None)
                    self._adapters.pop(name, None)

    def catalog(self) -> EventCatalog:
        with self._lock:
            definitions = (
                {event.name: event for event in self.parent.catalog().events}
                if self.parent
                else {}
            )
            definitions.update(self._definitions)
            return EventCatalog(
                events=[
                    definitions[name].model_copy(deep=True)
                    for name in sorted(definitions)
                ]
            )


builtin_events = EventRegistry()

for name in ("on_load", "on_unload", "on_manager_startup"):
    builtin_events.register(EventDefinition(name=name, phase="lifecycle", public=False))
