"""Standardized declarative decorators for plugin capabilities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, TypeVar

if TYPE_CHECKING:
    from pydantic import BaseModel

F = TypeVar("F", bound=Callable[..., Any])


def scheduled_task(
    name: str | None = None,
    *,
    options_model: type[BaseModel] | None = None,
    timeout_seconds: float = 300,
    requires_server_lock: bool = True,
    with_context: bool = False,
    description: str = "",
) -> Callable[[F], F]:
    """Declare a periodic cron-scheduled plugin task.

    The task name is automatically prefixed with ``<plugin_name>:`` when a
    namespace prefix is omitted.
    """

    def decorator(func: F) -> F:
        task_name = name if name is not None else getattr(func, "__name__", "")
        configs = list(getattr(func, "_scheduled_task_configs", ()))
        configs.append(
            {
                "name": task_name,
                "options_model": options_model,
                "timeout_seconds": timeout_seconds,
                "requires_server_lock": requires_server_lock,
                "with_context": with_context,
                "description": description
                or (getattr(func, "__doc__", "") or "").strip(),
            }
        )
        setattr(func, "_scheduled_task_configs", tuple(configs))
        return func

    return decorator


def diagnostic_provider(name: str | None = None) -> Callable[[F], F]:
    """Declare an asynchronous or synchronous diagnostic provider on a plugin method."""

    def decorator(func: F) -> F:
        provider_name = name if name is not None else getattr(func, "__name__", "")
        names = list(getattr(func, "_diagnostic_provider_names", ()))
        names.append(provider_name)
        setattr(func, "_diagnostic_provider_names", tuple(names))
        return func

    return decorator


def data_provider(topic: str | None = None) -> Callable[[F], F]:
    """Declare a WebSocket topic data provider on a plugin method."""

    def decorator(func: F) -> F:
        topic_name = topic if topic is not None else getattr(func, "__name__", "")
        topics = list(getattr(func, "_data_provider_topics", ()))
        topics.append(topic_name)
        setattr(func, "_data_provider_topics", tuple(topics))
        return func

    return decorator


websocket_provider = data_provider
