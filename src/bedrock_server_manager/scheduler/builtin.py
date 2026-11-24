"""Registration of built-in server and system maintenance tasks."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from ..utils.threads import run_in_thread
from .runner import DeferredRun
from .tasks import (
    BackupScheduleOptions,
    PruneDownloadsScheduleOptions,
    VerifyScheduleOptions,
)

if TYPE_CHECKING:
    from .service import Scheduler

logger = logging.getLogger(__name__)


def register_builtin_tasks(scheduler: Scheduler) -> None:
    """Register core backup/restore, server management, and system APIs into the scheduler."""

    def _validate_backup_options(
        sched: Scheduler, server_name: str, options: dict[str, Any]
    ) -> None:
        from ..backups.selection import selection
        from ..error import BackupRestoreError, UserInputError
        from ..models.backup_restore import CreateSnapshotRequest

        allowed = {"encrypted", "mode", "components"}
        if set(options) - allowed:
            raise UserInputError("Unknown scheduled task option")
        try:
            CreateSnapshotRequest(server_name=server_name or "all", **options)
            selection(
                sched.context.settings,
                options.get("mode"),
                options.get("components"),
            )
        except (ValueError, TypeError, BackupRestoreError) as error:
            raise UserInputError(
                "Invalid backup content or encryption options"
            ) from error

    async def _reconcile_backup_slot(server: Any, slot: str) -> bool:
        async with server.operation_lock:

            def _has_slot_archive() -> bool:
                value = server.backups.catalog.load()
                return any(
                    item.get("schedule_slot") == slot
                    and (server.backups.catalog.directory / filename).is_file()
                    for filename, item in value["archives"].items()
                )

            return await run_in_thread(_has_slot_archive)

    def _validate_verify_options(
        sched: Scheduler, server_name: str, options: dict[str, Any]
    ) -> None:
        from ..error import UserInputError

        allowed = {"minimum_age_hours"}
        if set(options) - allowed:
            raise UserInputError("Unknown scheduled task option")
        age = options.get("minimum_age_hours", 168)
        if type(age) is not int or not 0 <= age <= 8760:
            raise UserInputError("Verification age must be an integer from 0 to 8760")

    async def _verify_backups_handler(
        *, server_name: str, options: dict[str, Any]
    ) -> None:
        server = scheduler.context.get_server(server_name, require_installation=False)
        age = options.get("minimum_age_hours", 168)
        failed = 0
        for item in await server.backups.list_snapshots():
            if server.operation_lock.waiting:
                raise DeferredRun("Verification yielded to interactive work")
            checked = item.verification.verified_at
            if (
                item.verification.status != "verified"
                or not checked
                or datetime.now(timezone.utc) - datetime.fromisoformat(checked)
                >= timedelta(hours=age)
            ):
                try:
                    await server.backups.verify_snapshot(item.backup_id)
                except Exception as error:
                    scheduler._log_failures.report(
                        "verification", "Scheduler %s failed: %s", error
                    )
                    failed += 1
        if failed:
            raise RuntimeError(
                "Some scheduled archive verifications failed; inspect backup health"
            )

    scheduler.tasks.register_api_task(
        "backup:create",
        "backup_restore.create_server_backup",
        owner="application",
        options_model=BackupScheduleOptions,
        default_options={"purpose": "scheduled"},
        slot_field="schedule_slot",
        timeout_seconds=None,
        requires_server_lock=True,
        manage_server_lock=False,
        exclude_unset_options=True,
        reconcile_handler=_reconcile_backup_slot,
        options_validator=_validate_backup_options,
        description="Create a scheduled server snapshot archive.",
        failure_message="Scheduled backup did not complete",
    )
    scheduler.tasks.register(
        "backup:verify",
        _verify_backups_handler,
        owner="application",
        options_model=VerifyScheduleOptions,
        timeout_seconds=None,
        requires_server_lock=True,
        manage_server_lock=False,
        exclude_unset_options=True,
        options_validator=_validate_verify_options,
        description="Verify snapshot archive integrity for backups older than minimum_age_hours.",
    )
    scheduler.tasks.register_api_task(
        "backup:prune",
        "backup_restore.prune_old_backups",
        owner="application",
        timeout_seconds=None,
        requires_server_lock=True,
        manage_server_lock=False,
        description="Prune old backups according to server retention policies.",
    )
    scheduler.tasks.register_api_task(
        "server:start",
        "server.start",
        owner="application",
        requires_server_lock=True,
        manage_server_lock=False,
        description="Start the Bedrock server.",
    )
    scheduler.tasks.register_api_task(
        "server:stop",
        "server.stop",
        owner="application",
        requires_server_lock=True,
        manage_server_lock=False,
        description="Stop the Bedrock server.",
    )
    scheduler.tasks.register_api_task(
        "server:restart",
        "server.restart",
        owner="application",
        requires_server_lock=True,
        manage_server_lock=False,
        description="Restart the Bedrock server.",
    )
    scheduler.tasks.register_api_task(
        "server:update",
        "install.update_server",
        owner="application",
        timeout_seconds=None,
        requires_server_lock=True,
        manage_server_lock=False,
        description="Check for and install Bedrock server updates (with pre-update backup).",
    )
    scheduler.tasks.register_api_task(
        "server:send_command",
        "server.send_command",
        owner="application",
        requires_server_lock=False,
        manage_server_lock=False,
        description="Send a console command to a running Bedrock server.",
    )
    scheduler.tasks.register_api_task(
        "world:export",
        "world.export_world",
        owner="application",
        timeout_seconds=None,
        requires_server_lock=True,
        manage_server_lock=False,
        description="Export the active server world to a .mcworld archive.",
    )
    scheduler.tasks.register_api_task(
        "world:reset",
        "world.reset_world",
        owner="application",
        timeout_seconds=None,
        requires_server_lock=True,
        manage_server_lock=False,
        description="Reset the active server world directory so it regenerates on next start.",
    )
    scheduler.tasks.register_api_task(
        "player:scan",
        "player.scan_and_update_player_db",
        owner="application",
        timeout_seconds=None,
        requires_server_lock=False,
        manage_server_lock=False,
        description="Scan server logs to discover and update known players in the database.",
    )

    async def _prune_downloads_handler(
        *, server_name: str, options: dict[str, Any]
    ) -> None:
        import os

        import aiofiles.ospath

        base_dir = scheduler.context.settings.get("paths.downloads")
        if not base_dir:
            raise RuntimeError("DOWNLOAD_DIR setting is missing in configuration")
        channel = options.get("directory")
        keep = options.get("keep_count")
        channels = [channel] if channel else ["stable", "preview"]
        for subdir in channels:
            target_dir = os.path.normpath(os.path.join(base_dir, subdir))
            if not os.path.abspath(target_dir).startswith(
                os.path.abspath(base_dir) + os.sep
            ):
                raise RuntimeError(f"Invalid download cache channel: {subdir}")
            if not await aiofiles.ospath.isdir(target_dir):
                continue
            res = await scheduler.context.api.misc.prune_download_cache(
                {"download_dir": target_dir, "keep_count": keep}
            )
            if res.status not in ("success", "skipped"):
                raise RuntimeError(
                    res.message
                    or f"Scheduled download cache prune failed for '{subdir}'"
                )

    scheduler.tasks.register(
        "system:prune_downloads",
        _prune_downloads_handler,
        owner="application",
        options_model=PruneDownloadsScheduleOptions,
        timeout_seconds=None,
        requires_server_lock=False,
        manage_server_lock=False,
        exclude_unset_options=True,
        description="Prune old downloaded Bedrock server installer archives.",
    )
