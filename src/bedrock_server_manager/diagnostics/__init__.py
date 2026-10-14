"""Metadata diagnostics independent of HTTP and application context."""

from typing import TYPE_CHECKING

from .models import DiagnosticOptions, PluginValues

if TYPE_CHECKING:
    from .service import Diagnostics

__all__ = ["DiagnosticOptions", "Diagnostics", "PluginValues"]


def __getattr__(name: str):
    """Load the runtime service only when requested, keeping model imports lightweight."""
    if name == "Diagnostics":
        from .service import Diagnostics

        return Diagnostics
    raise AttributeError(name)
