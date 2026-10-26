"""Portable IANA timezone resolution; never convert recurring schedules to fixed offsets."""

from datetime import timezone, tzinfo
from functools import lru_cache
from importlib import resources
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfo as FileZoneInfo
from zoneinfo import ZoneInfoNotFoundError, available_timezones


@lru_cache(maxsize=512)
def resolve_timezone(name: str) -> tzinfo:
    """Use built-in UTC, system IANA data, or the declared bundled tzdata package."""
    if name in ("UTC", "Etc/UTC"):
        return timezone.utc
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        # Some hosts have an incomplete system TZPATH. Read the portable package
        # explicitly before reporting an unsupported region.
        if (
            "\\" in name
            or ":" in name
            or any(part in ("", ".", "..") for part in name.split("/"))
        ):
            raise ValueError("Choose a valid IANA timezone") from None
        try:
            resource = resources.files("tzdata.zoneinfo").joinpath(*name.split("/"))
            with resource.open("rb") as stream:
                return FileZoneInfo.from_file(stream, key=name)
        except (ModuleNotFoundError, FileNotFoundError, ValueError, OSError):
            raise ZoneInfoNotFoundError(name) from None


def timezone_database_available() -> bool:
    try:
        resolve_timezone("America/Los_Angeles")
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


@lru_cache(maxsize=1)
def _timezone_names() -> tuple[str, ...]:
    return tuple(sorted(available_timezones() | {"UTC", "Etc/UTC"}))


def schedule_timezones() -> list[str]:
    """Return a fresh copy of the process's supported regional timezone names."""
    return list(_timezone_names())
