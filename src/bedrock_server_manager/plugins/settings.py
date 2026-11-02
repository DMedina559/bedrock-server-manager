"""Reusable Pydantic types and utilities for plugin settings schemas and evolution."""

import logging
from typing import (
    Annotated,
    Any,
    Dict,
    Union,
    get_args,
    get_origin,
)

from pydantic import AfterValidator, BaseModel, Field, ValidationInfo

logger = logging.getLogger(__name__)


def _existing_server(value: str, info: ValidationInfo) -> str:
    if info.context is not None and value not in info.context["server_names"]:
        raise ValueError("Select an existing server.")
    return value


ExistingServerName = Annotated[
    str,
    Field(
        strict=True,
        min_length=1,
        pattern=r"^[a-zA-Z0-9_-]+$",
        json_schema_extra={"x-bsm-server-name": True},
    ),
    AfterValidator(_existing_server),
]


def resolve_model_class(annotation: Any) -> type[BaseModel] | None:
    """Resolve a BaseModel class from a type annotation, unwrapping Optionals and Unions."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    origin = get_origin(annotation)
    if origin is Union:
        for arg in get_args(annotation):
            if (
                arg is not type(None)
                and isinstance(arg, type)
                and issubclass(arg, BaseModel)
            ):
                return arg
    return None


def get_field_map(model_cls: type[BaseModel]) -> dict[str, Any]:
    """Map valid field names and aliases to their FieldInfo objects."""
    mapping: dict[str, Any] = {}
    for name, field in model_cls.model_fields.items():
        mapping[name] = field
        if field.alias:
            mapping[field.alias] = field
        if isinstance(field.validation_alias, str):
            mapping[field.validation_alias] = field
    return mapping


def prune_dropped_fields(model_cls: Any, data: Any) -> tuple[Any, set[str]]:
    """Recursively prune fields from data that are not declared in model_cls.

    Returns a tuple of (pruned_data, set_of_dropped_field_paths).
    """
    dropped: set[str] = set()
    if not isinstance(data, dict):
        return data, dropped

    resolved_root = resolve_model_class(model_cls)
    if resolved_root is None:
        return data, dropped

    field_map = get_field_map(resolved_root)
    pruned: dict[str, Any] = {}

    for k, v in data.items():
        if k not in field_map:
            dropped.add(k)
        else:
            field = field_map[k]
            sub_model = resolve_model_class(field.annotation)
            child_origin = get_origin(field.annotation)

            if sub_model is not None and isinstance(v, dict):
                sub_v, sub_dropped = prune_dropped_fields(sub_model, v)
                pruned[k] = sub_v
                dropped.update(f"{k}.{d}" for d in sub_dropped)
            elif child_origin in (list, set, tuple) and isinstance(
                v, (list, set, tuple)
            ):
                item_types = get_args(field.annotation)
                item_model = resolve_model_class(item_types[0]) if item_types else None
                if item_model is not None:
                    new_list = []
                    for idx, item in enumerate(v):
                        sub_v, sub_dropped = prune_dropped_fields(item_model, item)
                        new_list.append(sub_v)
                        dropped.update(f"{k}[{idx}].{d}" for d in sub_dropped)
                    pruned[k] = new_list
                else:
                    pruned[k] = v
            elif child_origin in (dict, Dict) and isinstance(v, dict):
                dict_args = get_args(field.annotation)
                val_model = (
                    resolve_model_class(dict_args[1]) if len(dict_args) >= 2 else None
                )
                if val_model is not None:
                    new_dict = {}
                    for dict_k, dict_v in v.items():
                        sub_v, sub_dropped = prune_dropped_fields(val_model, dict_v)
                        new_dict[dict_k] = sub_v
                        dropped.update(f"{k}.{dict_k}.{d}" for d in sub_dropped)
                    pruned[k] = new_dict
                else:
                    pruned[k] = v
            else:
                pruned[k] = v

    return pruned, dropped
