"""Declarations are independent of plugin discovery and HTTP routing."""

from functools import reduce
from operator import or_
from typing import Any

from pydantic import BaseModel, TypeAdapter

from .models import EventCatalog, EventDefinition


class EventRegistry:
    def __init__(self, parent: "EventRegistry | None" = None):
        self.parent = parent
        self._definitions: dict[str, EventDefinition] = {}
        self._models: dict[str, list[type[BaseModel]]] = {}

    def register(
        self, definition: EventDefinition, payload_model: type[BaseModel] | None = None
    ) -> None:
        existing = self._definitions.get(definition.name)
        if existing is not None and (
            existing.phase != definition.phase
            or existing.identity_keys != definition.identity_keys
        ):
            raise ValueError(f"Conflicting event definition: {definition.name}")
        definition = definition.model_copy(deep=True)
        if payload_model is not None:
            models = self._models.setdefault(definition.name, [])
            if payload_model not in models:
                models.append(payload_model)
            adapter: TypeAdapter[Any] = TypeAdapter(reduce(or_, models))
            definition.payload_schema = adapter.json_schema(mode="serialization")
        self._definitions[definition.name] = definition

    def definition(self, name: str) -> EventDefinition:
        definition = self._definitions.get(name)
        if definition is None and self.parent is not None:
            return self.parent.definition(name)
        return (definition or EventDefinition(name=name)).model_copy(deep=True)

    def prepare(self, name: str, data: dict[str, Any]) -> Any:
        model = self._models.get(name)
        if model is None and self.parent is not None:
            return self.parent.prepare(name, data)
        if model:
            adapter: TypeAdapter[Any] = TypeAdapter(reduce(or_, model))
            return adapter.validate_python(data)
        return data

    def payload_models(self, name: str) -> tuple[type[BaseModel], ...]:
        """Read payload model variants for contract tools and documentation."""
        if name in self._models:
            return tuple(self._models[name])
        return self.parent.payload_models(name) if self.parent else ()

    def declared(self, name: str) -> bool:
        return name in self._definitions or (
            self.parent is not None and self.parent.declared(name)
        )

    def remove_owner(self, owner: str) -> None:
        for name, definition in list(self._definitions.items()):
            if definition.owner == owner:
                self._definitions.pop(name)
                self._models.pop(name, None)

    def catalog(self) -> EventCatalog:
        definitions = (
            {event.name: event for event in self.parent.catalog().events}
            if self.parent
            else {}
        )
        definitions.update(self._definitions)
        return EventCatalog(
            events=[
                definitions[name].model_copy(deep=True) for name in sorted(definitions)
            ]
        )


builtin_events = EventRegistry()

for name in ("on_load", "on_unload", "on_manager_startup"):
    builtin_events.register(EventDefinition(name=name, phase="lifecycle", public=False))
