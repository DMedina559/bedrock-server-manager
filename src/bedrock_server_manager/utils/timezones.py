"""Resolve schedule timezones consistently across Windows and Unix hosts."""

from datetime import timezone, tzinfo
from zoneinfo import ZoneInfo


def resolve_timezone(name: str) -> tzinfo:
    """UTC needs no external timezone database; named regions use IANA rules."""
    if name in ("UTC", "Etc/UTC"):
        return timezone.utc
    return ZoneInfo(name)
