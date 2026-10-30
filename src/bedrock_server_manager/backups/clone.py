"""Prepare an isolated destination without automatically applying a restore."""

import json
import os
from pathlib import Path
from uuid import uuid4

from ..api.models.backup_restore import PrepareBackupCopyResponse
from ..api.models.install import InstallNewServerRequest
from ..error import BackupRestoreError
from ..utils.io import temporary_directory
from ..utils.server import core_validate_server_name_format
from ..utils.threads import run_in_thread
from .archive import write_archive
from .credentials import key_id, private_directory
from .models import PREFIXES
from .recovery import sync_tree
from .server import inventory


async def prepare_copy(request, context) -> PrepareBackupCopyResponse:
    from ..api.install import install_new_server

    core_validate_server_name_format(request.target_server)
    if request.target_server in context.state.servers.servers:
        raise BackupRestoreError("Choose a new, unused server name.")
    target_directory = (
        Path(context.settings.get("paths.servers")) / request.target_server
    )
    if target_directory.exists():
        raise BackupRestoreError(
            "Destination directory already exists; choose an unused server name."
        )
    source = context.get_server(request.server_name, require_installation=False).backups
    async with source.server.operation_lock:
        archive = source.resolve_backup(request.backup_id)
        key = request.recovery_key.get_secret_value() if request.recovery_key else None
        password = await run_in_thread(source._password, archive, key)
        async with temporary_directory(
            prefix=".bsm-copy-stage-", parent=archive.parent
        ) as directory:
            staging = Path(directory)
            manifest = await run_in_thread(
                source.unpack_snapshot, archive, staging, password
            )
            if manifest.components.get("server_directory") == "included":
                raise BackupRestoreError(
                    "Use a selected-components backup to prepare a separate server copy."
                )
            if manifest.components["server.properties"] != "included":
                raise BackupRestoreError("A server copy requires server.properties.")
            # Refuse conflicting ports before installing anything.
            for name in context.state.servers.servers:
                server = context.get_server(name, require_installation=False)
                properties = Path(server.paths.server_properties_path)
                if not properties.is_file():
                    continue
                text = await run_in_thread(properties.read_text, encoding="utf-8-sig")
                for line in text.splitlines():
                    if line.startswith(
                        ("server-port=", "server-portv6=")
                    ) and line.partition("=")[2].strip() in (
                        str(request.server_port),
                        str(request.server_portv6),
                    ):
                        raise BackupRestoreError(
                            "Choose ports that are not used by another registered server."
                        )
            await context.task_manager.report_stage(
                "Installing stopped destination server"
            )
            result = await install_new_server(
                InstallNewServerRequest(
                    server_name=request.target_server,
                    target_version=request.target_version,
                ),
                app_context=context,
            )
            if result.status != "success":
                raise BackupRestoreError("Destination installation did not complete.")
            destination = context.get_server(request.target_server).backups
            async with destination.server.operation_lock:
                properties = staging / PREFIXES["server.properties"]
                text = await run_in_thread(properties.read_text, encoding="utf-8-sig")
                lines = [
                    line
                    for line in text.splitlines()
                    if not line.startswith(("server-port=", "server-portv6="))
                ]
                lines.extend(
                    (
                        f"server-port={request.server_port}",
                        f"server-portv6={request.server_portv6}",
                    )
                )
                await run_in_thread(
                    properties.write_text, "\n".join(lines) + "\n", encoding="utf-8"
                )
                if manifest.components["bsm_settings"] == "included":
                    path = staging / PREFIXES["bsm_settings"]
                    exported = json.loads(await run_in_thread(path.read_bytes))
                    exported["autostart"] = False
                    await run_in_thread(
                        path.write_text, json.dumps(exported), encoding="utf-8"
                    )
                files, directories = await run_in_thread(
                    inventory, staging, manifest.components
                )
                manifest = manifest.model_copy(
                    update={
                        "backup_id": uuid4(),
                        "files": files,
                        "directories": directories,
                        "warnings": [
                            *manifest.warnings,
                            "Prepared copy uses new ports and disables autostart; review before restoring.",
                        ],
                    }
                )
                root = await run_in_thread(
                    private_directory, Path(destination._directory())
                )
                filename = (
                    manifest.created_at.strftime("%Y%m%dT%H%M%SZ")
                    + "_"
                    + uuid4().hex
                    + ".bsmbackup"
                )
                temporary = staging / "copy.bsmbackup"
                await run_in_thread(
                    write_archive,
                    staging,
                    temporary,
                    manifest,
                    password,
                    None if password is None else key_id(password),
                )
                verify = await run_in_thread(private_directory, staging / "verify-copy")
                await run_in_thread(
                    destination.unpack_snapshot, temporary, verify, password
                )
                await run_in_thread(sync_tree, temporary)
                await run_in_thread(os.replace, temporary, root / filename)
                await run_in_thread(
                    destination._record_verified, root / filename, manifest
                )
                await destination.pin_snapshot(filename, True)
    return PrepareBackupCopyResponse(
        server_name=request.target_server,
        backup_id=filename,
        message="Stopped destination prepared. Review and restore the copied archive on that server. The archive is pinned; no restore has run.",
    )
