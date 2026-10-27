"""Resolve backup content without classifying bundled packs."""

from pydantic import ValidationError

from ..error import BackupRestoreError
from .contents import BackupContentSelection
from .models import BASE_COMPONENTS, PACK_COMPONENTS, BackupMode, Component


def selection(
    settings, mode=None, components=None, include_packs=None
) -> tuple[BackupMode, list[Component]]:
    mode = mode or settings.get("backups.mode", "selected")
    if mode not in ("world", "selected", "full"):
        raise BackupRestoreError("Choose world, selected, or full backup mode.")
    if components is not None and mode != "selected":
        raise BackupRestoreError("Components are only supported in selected mode.")
    if include_packs is not None and (mode != "selected" or components is not None):
        raise BackupRestoreError(
            "Use components instead of include_packs with an explicit selection."
        )
    if mode == "world":
        return mode, ["world"]
    if mode == "full":
        return mode, ["server_directory", "bsm_settings"]
    chosen = list(
        components
        if components is not None
        else settings.get("backups.components", list(BASE_COMPONENTS))
    )
    if include_packs is not None or (
        components is None and settings.get("backups.include_server_packs", False)
    ):
        chosen = [c for c in chosen if c not in PACK_COMPONENTS]
        if include_packs is not False:
            chosen.extend(PACK_COMPONENTS)
    try:
        validated = BackupContentSelection(mode=mode, components=chosen)
    except ValidationError as error:
        raise BackupRestoreError(
            "Select at least one valid component without duplicates."
        ) from error
    return validated.mode, list(validated.components)


def server_entries(root):
    """Reserve BSM capture, staging and recovery storage at the server root."""
    return sorted(
        (p for p in root.iterdir() if not p.name.startswith(".bsm-")),
        key=lambda p: p.name,
    )
