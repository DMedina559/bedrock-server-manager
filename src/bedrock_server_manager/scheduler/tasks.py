"""Unified task definition registry and options schemas for the scheduler."""

from __future__ import annotations

import inspect
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from pydantic import BaseModel, ConfigDict, Field, create_model

from ..backups.contents import BackupComponents, BackupMode
from .runner import DeferredRun

if TYPE_CHECKING:
    from ..context import AppContext

logger = logging.getLogger(__name__)


class BackupScheduleOptions(BaseModel):
    """Serializable options for scheduled server snapshot creation."""

    model_config = ConfigDict(extra="forbid", strict=True)

    encrypted: bool | None = None
    mode: BackupMode | None = None
    components: BackupComponents | None = None


class VerifyScheduleOptions(BaseModel):
    """Serializable options for scheduled backup archive verification."""

    model_config = ConfigDict(extra="forbid", strict=True)

    minimum_age_hours: int = Field(default=168, ge=0, le=8760)


class PruneDownloadsScheduleOptions(BaseModel):
    """Serializable options for scheduled download cache pruning."""

    model_config = ConfigDict(extra="forbid", strict=True)

    directory: str | None = Field(
        default=None,
        pattern=r"^(stable|preview)$",
        description="Optional download cache channel ('stable' or 'preview'); prunes both when omitted.",
    )
    keep_count: int | None = Field(
        default=None,
        ge=0,
        le=1000,
        description="Number of recent installer archives to retain per channel.",
    )


class EmptyScheduleOptions(BaseModel):
    """Options model for scheduled API tasks that take only server_name."""

    model_config = ConfigDict(extra="forbid", strict=True)


@dataclass(frozen=True)
class TaskDefinition:
    """Unified registration entry for built-in and plugin scheduled tasks."""

    name: str
    handler: Callable[..., Awaitable[Any]]
    owner: str = "application"
    generation: int = 0
    options_model: type[BaseModel] | None = None
    timeout_seconds: float | None = 300
    requires_server_lock: bool = True
    with_context: bool = False
    manage_server_lock: bool = True
    exclude_unset_options: bool = False
    reconcile_handler: Callable[[Any, str], Awaitable[bool]] | None = None
    options_validator: Callable[[Any, str, dict[str, Any]], None] | None = None
    description: str = ""
    api_method_name: str | None = None


def _derive_api_options_model(
    request_cls: type[BaseModel],
    default_options: dict[str, Any] | None = None,
) -> type[BaseModel]:
    """Build a schedule options Pydantic model from an APIRequest model."""
    fields: dict[str, Any] = {}
    defaults = default_options or {}
    for field_name, field_info in request_cls.model_fields.items():
        if field_name in {"server_name", "schedule_slot"}:
            continue
        annotation = field_info.annotation or Any
        if field_name in defaults:
            fields[field_name] = (
                annotation,
                Field(default=defaults[field_name], description=field_info.description),
            )
        elif field_info.is_required():
            fields[field_name] = (
                annotation,
                Field(..., description=field_info.description),
            )
        elif field_info.default_factory is not None:
            fields[field_name] = (
                annotation,
                Field(
                    default_factory=field_info.default_factory,
                    description=field_info.description,
                ),
            )
        else:
            fields[field_name] = (
                annotation,
                Field(
                    default=field_info.default,
                    description=field_info.description,
                ),
            )
    if not fields:
        return EmptyScheduleOptions
    return create_model(
        f"{request_cls.__name__}ScheduleOptions",
        __config__=ConfigDict(extra="forbid", strict=True),
        **fields,
    )


class TaskRegistry:
    """Unified registry for scheduler task definitions."""

    def __init__(self, context: AppContext):
        self.context = context
        self._handlers: dict[str, TaskDefinition] = {}

    @property
    def handlers(self) -> dict[str, TaskDefinition]:
        """Return the mapping of registered task definitions."""
        return self._handlers

    def get_task_definition(self, name: str) -> TaskDefinition | None:
        """Return the active ``TaskDefinition`` for ``name`` if available."""
        entry = self._handlers.get(name)
        if entry is None:
            return None
        if entry.owner != "application":
            try:
                self.context.events.check_owner(entry.owner, entry.generation)
            except RuntimeError:
                self._handlers.pop(name, None)
                return None
        return entry

    def available(self, name: str) -> bool:
        """Return whether a task definition exists and its owning plugin is active."""
        return self.get_task_definition(name) is not None

    def remove_owner(self, owner: str) -> None:
        """Remove all scheduled task definitions registered by ``owner``."""
        for name, entry in list(self._handlers.items()):
            if entry.owner == owner:
                self._handlers.pop(name, None)

    def register(
        self,
        name: str,
        handler: Callable[..., Awaitable[Any]],
        *,
        owner: str = "application",
        generation: int = 0,
        options_model: type[BaseModel] | None = None,
        timeout_seconds: float | None = 300,
        requires_server_lock: bool = True,
        with_context: bool = False,
        manage_server_lock: bool | None = None,
        exclude_unset_options: bool = False,
        reconcile_handler: Callable[[Any, str], Awaitable[bool]] | None = None,
        options_validator: Callable[[Any, str, dict[str, Any]], None] | None = None,
        description: str = "",
        api_method_name: str | None = None,
    ) -> TaskDefinition:
        """Register an async scheduled task handler in the unified task registry."""
        if not inspect.iscoroutinefunction(handler):
            raise TypeError("Scheduled task handlers must be async functions")

        if owner.startswith("plugin:"):
            plugin_prefix = owner.removeprefix("plugin:")
            if ":" not in name and re.fullmatch(r"[a-zA-Z0-9_.-]+", name):
                name = f"{plugin_prefix}:{name}"

        if (
            not re.fullmatch(r"[a-zA-Z0-9_.-]+:[a-zA-Z0-9_.-]+", name)
            or len(name) > 160
        ):
            raise ValueError(
                "Scheduled task names require a namespace and name within 160 characters"
            )
        if owner.startswith("plugin:") and not name.startswith(
            owner.removeprefix("plugin:") + ":"
        ):
            raise ValueError("Scheduled task names must use the plugin namespace")
        if name in self._handlers and self.available(name):
            raise ValueError("Scheduled task is already registered")

        if options_model is None:
            try:
                sig = inspect.signature(handler)
                opt_param = sig.parameters.get("options")
                if (
                    opt_param is not None
                    and inspect.isclass(opt_param.annotation)
                    and issubclass(opt_param.annotation, BaseModel)
                ):
                    options_model = opt_param.annotation
                if not with_context and "execution_context" in sig.parameters:
                    with_context = True
            except (ValueError, TypeError):
                pass

        if options_model is not None and (
            not inspect.isclass(options_model)
            or not issubclass(options_model, BaseModel)
        ):
            raise TypeError("Task options_model must be a Pydantic model class")
        if timeout_seconds is not None and (
            type(timeout_seconds) not in (int, float)
            or not 1 <= timeout_seconds <= 86400
        ):
            raise ValueError("Task timeout must be from 1 through 86400 seconds")
        if options_model is not None:
            options_model.model_json_schema()

        effective_manage_lock = (
            requires_server_lock if manage_server_lock is None else manage_server_lock
        )
        definition = TaskDefinition(
            name=name,
            handler=handler,
            owner=owner,
            generation=generation,
            options_model=options_model,
            timeout_seconds=timeout_seconds,
            requires_server_lock=requires_server_lock,
            with_context=with_context,
            manage_server_lock=effective_manage_lock,
            exclude_unset_options=exclude_unset_options,
            reconcile_handler=reconcile_handler,
            options_validator=options_validator,
            description=description,
            api_method_name=api_method_name,
        )
        self._handlers[name] = definition
        return definition

    def register_api_task(
        self,
        name: str,
        api_function: Callable[..., Any] | str,
        *,
        owner: str = "application",
        generation: int = 0,
        options_model: type[BaseModel] | None = None,
        default_options: dict[str, Any] | None = None,
        slot_field: str | None = None,
        timeout_seconds: float | None = 300,
        requires_server_lock: bool = True,
        manage_server_lock: bool = False,
        exclude_unset_options: bool = True,
        reconcile_handler: Callable[[Any, str], Awaitable[bool]] | None = None,
        options_validator: Callable[[Any, str, dict[str, Any]], None] | None = None,
        description: str = "",
        failure_message: str | None = None,
    ) -> TaskDefinition:
        """Register an API method to run as a scheduled task."""
        from importlib import import_module

        from ..api.contract import get_contract
        from ..plugins.api_bridge import _api_methods, _api_registry

        import_module("bedrock_server_manager.api")

        resolved_api_name: str | None = None
        resolved_domain: str | None = None
        resolved_method: str | None = None
        target_callable: Callable[..., Any] | None = None
        request_cls: type[BaseModel] | None = None

        if isinstance(api_function, str):
            if "." in api_function:
                domain_part, method_part = api_function.split(".", 1)
                reg_name = (
                    _api_methods().get(domain_part, {}).get(method_part, method_part)
                )
                entry = _api_registry.get(reg_name)
                if entry is None:
                    raise ValueError(f"Unknown API method '{api_function}'")
                resolved_api_name = reg_name
                resolved_domain = domain_part
                resolved_method = method_part
                target_callable = entry[0]
            else:
                entry = _api_registry.get(api_function)
                if entry is None:
                    raise ValueError(f"Unknown API method '{api_function}'")
                resolved_api_name = api_function
                resolved_domain = entry[4]
                resolved_method = next(
                    (
                        m
                        for m, r in _api_methods().get(resolved_domain, {}).items()
                        if r == api_function
                    ),
                    api_function,
                )
                target_callable = entry[0]
        elif callable(api_function):
            target_callable = api_function
            for reg_name, entry in _api_registry.items():
                if inspect.unwrap(entry[0]) is inspect.unwrap(api_function):
                    resolved_api_name = reg_name
                    resolved_domain = entry[4]
                    resolved_method = next(
                        (
                            m
                            for m, r in _api_methods().get(resolved_domain, {}).items()
                            if r == reg_name
                        ),
                        reg_name,
                    )
                    break
        else:
            raise TypeError("api_function must be a callable or registered API name")

        plugin_api_call = None
        if owner.startswith("plugin:"):
            from ..plugins.api_bridge import create_app_api

            self.context.events.check_owner(owner, generation)
            if resolved_api_name is not None:
                entry = _api_registry[resolved_api_name]
                domain = entry[4]
                method = next(
                    (
                        m
                        for m, r in _api_methods().get(domain, {}).items()
                        if r == resolved_api_name
                    ),
                    resolved_api_name,
                )
                bridge = create_app_api(owner.removeprefix("plugin:"), self.context)
                # Resolving through the bridge rejects internal methods immediately.
                plugin_api_call = getattr(getattr(bridge, domain), method)
            elif (
                target_callable is not None
                and "app_context" in inspect.signature(target_callable).parameters
            ):
                raise TypeError(
                    "Plugin task callbacks must not request internal application context"
                )

        if target_callable is not None:
            unwrapped = getattr(target_callable, "__wrapped__", target_callable)
            try:
                contract = get_contract(unwrapped) or get_contract(target_callable)
            except (TypeError, NameError):
                contract = None
            if contract is not None:
                request_cls = contract[0]
            else:
                try:
                    sig = inspect.signature(target_callable)
                    first_param = next(iter(sig.parameters.values()), None)
                    if (
                        first_param is not None
                        and inspect.isclass(first_param.annotation)
                        and issubclass(first_param.annotation, BaseModel)
                    ):
                        request_cls = first_param.annotation
                except (ValueError, TypeError):
                    pass

        if options_model is None and request_cls is not None:
            options_model = _derive_api_options_model(request_cls, default_options)

        doc = description
        if not doc and target_callable is not None:
            raw_doc = inspect.getdoc(target_callable) or ""
            doc = raw_doc.strip().split("\n")[0] if raw_doc else ""

        err_msg = failure_message or f"Scheduled task '{name}' did not complete"

        async def _api_handler(
            *,
            server_name: str,
            options: dict[str, Any],
            execution_context: dict[str, Any] | None = None,
        ) -> Any:
            if owner.startswith("plugin:"):
                self.context.events.check_owner(owner, generation)
            payload: dict[str, Any] = dict(default_options or {})
            payload.update(options)
            if request_cls is None or "server_name" in request_cls.model_fields:
                payload["server_name"] = server_name
            if slot_field and execution_context and "slot" in execution_context:
                payload[slot_field] = execution_context["slot"]

            if plugin_api_call is not None:
                result = plugin_api_call(request=payload)
            elif (
                isinstance(api_function, str)
                and resolved_domain is not None
                and resolved_method is not None
            ):
                namespace = getattr(self.context.api, resolved_domain)
                api_call = getattr(namespace, resolved_method)
                result = api_call(request=payload)
            else:
                assert target_callable is not None
                sig = inspect.signature(target_callable)
                call_kwargs: dict[str, Any] = {}
                if "app_context" in sig.parameters:
                    call_kwargs["app_context"] = self.context
                if "plugin_name" in sig.parameters and owner.startswith("plugin:"):
                    call_kwargs["plugin_name"] = owner.removeprefix("plugin:")
                if "request" in sig.parameters:
                    result = target_callable(request=payload, **call_kwargs)
                else:
                    result = target_callable(payload, **call_kwargs)

            if inspect.isawaitable(result):
                result = await result

            if hasattr(result, "status"):
                status = getattr(result, "status")
                detail = getattr(result, "message", None)
                if status == "skipped":
                    try:
                        server = self.context.get_server(
                            server_name, require_installation=False
                        )
                    except Exception:
                        server = None
                    if (server is not None and server.operation_lock.locked()) or (
                        isinstance(detail, str)
                        and "already in progress" in detail.lower()
                    ):
                        raise DeferredRun(
                            "Scheduled task yielded to active server operation"
                        )
                    cleanup_outcome = getattr(
                        getattr(result, "result", None), "outcome", None
                    )
                    if cleanup_outcome == "noop" or (
                        isinstance(detail, str)
                        and "no backup directory" in detail.lower()
                    ):
                        return result
                if status != "success":
                    raise RuntimeError(f"{err_msg}: {detail}" if detail else err_msg)
            return result

        return self.register(
            name,
            _api_handler,
            owner=owner,
            generation=generation,
            options_model=options_model,
            timeout_seconds=timeout_seconds,
            requires_server_lock=requires_server_lock,
            with_context=bool(slot_field),
            manage_server_lock=manage_server_lock,
            exclude_unset_options=exclude_unset_options,
            reconcile_handler=reconcile_handler,
            options_validator=options_validator,
            description=doc,
            api_method_name=resolved_api_name
            or getattr(target_callable, "__name__", str(api_function)),
        )
