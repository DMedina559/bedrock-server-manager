"""Offline application-level backup and disaster recovery CLI commands with server backup parity."""

from __future__ import annotations

from pathlib import Path

import click
import questionary

from ..backups.app import (
    AppBackupCatalog,
    AppBackupManifest,
    ApplicationBackupError,
    assert_bsm_offline,
    create_app_backup,
    drill_app_backup,
    get_default_backups_dir,
    inspect_app_backup,
    list_app_backups,
    restore_app_backup,
)
from ..backups.models import APP_COMPONENTS, AppComponent, AppDrillResult, BackupHeader
from ..context import AppContext


def _resolve_context_paths(ctx: click.Context) -> tuple[str, str, str]:
    """Extract and resolve config_dir, data_dir, and db_url from context or defaults."""
    obj = ctx.obj or {}
    config_dir = obj.get("config_dir")
    data_dir = obj.get("data_dir")
    db_url = obj.get("db_url")

    context = AppContext(config_dir=config_dir, data_dir=data_dir, db_url=db_url)
    return context.config_dir, context.data_dir, context.db_url


def _format_size(bytes_size: int) -> str:
    """Format byte size into human-readable string."""
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(bytes_size)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.2f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.2f} TB"


def _display_manifest(
    hdr: BackupHeader,
    manifest: AppBackupManifest,
    archive_path: Path | None = None,
) -> None:
    """Pretty print manifest and header information."""
    click.echo()
    click.secho("=== Application Backup Details ===", fg="cyan", bold=True)
    if archive_path:
        click.echo(f"  Archive:       {archive_path.name}")
        click.echo(f"  Path:          {archive_path}")
    click.echo(f"  Backup ID:     {manifest.backup_id}")
    click.echo(
        f"  Created At:    {manifest.created_at.isoformat() if hasattr(manifest.created_at, 'isoformat') else manifest.created_at}"
    )
    click.echo(f"  BSM Version:   {manifest.bsm_version}")
    click.echo(f"  Database Type: {manifest.database_type}")
    click.echo(f"  DB Revision:   {manifest.alembic_version or 'Unstamped / None'}")

    enc_status = (
        f"Encrypted (Key ID: {hdr.key_id})"
        if hdr.encrypted
        else "Plaintext (Unencrypted)"
    )
    enc_color = "green" if hdr.encrypted else "yellow"
    click.echo(f"  Security:      {click.style(enc_status, fg=enc_color)}")

    click.echo(f"  Files Count:   {len(manifest.files)}")
    total_bytes = sum(f.size for f in manifest.files)
    click.echo(f"  Payload Size:  {_format_size(total_bytes)}")

    click.secho("\n  Components Included:", bold=True)
    for comp, status in manifest.components.items():
        color = "green" if status == "included" else "yellow"
        click.echo(f"    - {comp.ljust(12)}: {click.style(status, fg=color)}")
    click.echo()


def _display_drill_result(drill: AppDrillResult) -> None:
    """Pretty print recovery drill report."""
    click.echo()
    click.secho("=== Recovery Drill Report ===", fg="cyan", bold=True)
    status_str = (
        click.style("PASSED", fg="green", bold=True)
        if drill.status == "passed"
        else click.style("FAILED", fg="red", bold=True)
    )
    click.echo(f"  Drill Status:       {status_str}")
    click.echo(f"  Checked At:         {drill.checked_at}")
    click.echo(f"  Duration:           {drill.duration_ms} ms")
    click.echo(f"  Checked Files:      {drill.checked_files}")
    click.echo(f"  Checked Components: {', '.join(drill.checked_components)}")
    if drill.error:
        click.secho(f"  Error:              {drill.error}", fg="red")
    click.echo()


# =========================================================================
# Interactive Menu
# =========================================================================


def interactive_backup_menu(ctx: click.Context) -> None:
    """Interactive questionary menu for managing offline application backups."""
    config_dir, data_dir, db_url = _resolve_context_paths(ctx)

    click.echo()
    click.secho(
        "Bedrock Server Manager - Offline Application Backup", fg="cyan", bold=True
    )
    click.echo(
        "Complete instance backups, encryption, component control, and recovery drills.\n"
    )

    choices = [
        questionary.Choice("Create Application Backup", value="create"),
        questionary.Choice("Restore Application Backup", value="restore"),
        questionary.Choice("Inspect Backup Archive", value="inspect"),
        questionary.Choice("Run Recovery Drill (Isolated Test)", value="drill"),
        questionary.Choice("List Available Backups", value="list"),
        questionary.Choice("Exit", value="exit"),
    ]

    action = questionary.select("Select an action:", choices=choices).ask()
    if not action or action == "exit":
        return

    if action == "create":
        _interactive_create(config_dir, data_dir, db_url)
    elif action == "restore":
        _interactive_restore(config_dir, data_dir, db_url)
    elif action == "inspect":
        _interactive_inspect(config_dir, data_dir)
    elif action == "drill":
        _interactive_drill(config_dir, data_dir, db_url)
    elif action == "list":
        _interactive_list(config_dir, data_dir)


def _interactive_create(config_dir: str, data_dir: str, db_url: str) -> None:
    default_dir = get_default_backups_dir(config_dir, data_dir)
    default_output = str(default_dir)

    output_dir_str = questionary.text(
        "Destination directory (or leave default):",
        default=default_output,
    ).ask()
    if output_dir_str is None:
        return

    component_choices = [
        questionary.Choice(f"{c.capitalize()} ({c})", value=c, checked=True)
        for c in APP_COMPONENTS
    ]
    selected_components = questionary.checkbox(
        "Select components to include in the backup:",
        choices=component_choices,
    ).ask()
    if not selected_components:
        click.echo("Backup cancelled: no components selected.")
        return

    encrypt = questionary.confirm(
        "Encrypt backup using host keyring?", default=True
    ).ask()
    if encrypt is None:
        return

    recovery_key: str | None = None
    if not encrypt:
        use_custom_key = questionary.confirm(
            "Provide a custom recovery password instead?", default=False
        ).ask()
        if use_custom_key:
            recovery_key = questionary.password("Enter recovery key:").ask()

    click.echo("\nCreating application backup...")
    try:
        out_path = Path(output_dir_str)
        target_file = None if out_path.is_dir() or not out_path.suffix else out_path

        final_archive, manifest = create_app_backup(
            config_dir=config_dir,
            data_dir=data_dir,
            db_url=db_url,
            output_path=target_file,
            components=set(selected_components),
            encrypt=encrypt,
            recovery_key=recovery_key,
        )

        click.secho(
            f"\nApplication backup created successfully! Saved to: {final_archive}",
            fg="green",
        )
        hdr, _ = inspect_app_backup(
            final_archive, config_dir=config_dir, recovery_key=recovery_key
        )
        _display_manifest(hdr, manifest, final_archive)
    except ApplicationBackupError as e:
        click.secho(f"\nBackup failed: {e}", fg="red")
    except Exception as e:
        click.secho(f"\nUnexpected error during backup: {e}", fg="red")


def _select_archive_prompt(
    config_dir: str, data_dir: str, prompt_text: str
) -> Path | None:
    default_dir = get_default_backups_dir(config_dir, data_dir)
    backups = list_app_backups([default_dir], config_dir=config_dir)

    choices: list[questionary.Choice] = []
    for path, hdr, manifest in backups:
        created = (
            manifest.created_at.isoformat()[:19].replace("T", " ")
            if manifest and hasattr(manifest.created_at, "isoformat")
            else "Unknown date"
        )
        enc_tag = " [Encrypted]" if hdr.encrypted else ""
        label = f"{path.name} ({created}){enc_tag}"
        choices.append(questionary.Choice(label, value=path))

    choices.append(questionary.Choice("Enter custom archive path...", value="custom"))
    choices.append(questionary.Choice("Cancel", value=None))

    selected = questionary.select(prompt_text, choices=choices).ask()
    if not selected:
        return None

    if selected == "custom":
        custom_path_str = questionary.text("Enter path to backup archive:").ask()
        if not custom_path_str:
            return None
        selected = Path(custom_path_str)

    res_path = Path(selected) if not isinstance(selected, Path) else selected
    if not res_path.is_file():
        click.secho(f"File not found: {res_path}", fg="red")
        return None
    return res_path


def _interactive_restore(config_dir: str, data_dir: str, db_url: str) -> None:
    selected = _select_archive_prompt(config_dir, data_dir, "Select backup to restore:")
    if not selected:
        return

    recovery_key: str | None = None
    try:
        hdr, manifest = inspect_app_backup(selected, config_dir=config_dir)
    except ApplicationBackupError:
        recovery_key = questionary.password(
            "Archive is encrypted. Enter recovery key:"
        ).ask()
        if not recovery_key:
            return
        hdr, manifest = inspect_app_backup(selected, recovery_key=recovery_key)

    _display_manifest(hdr, manifest, selected)

    # Component selection
    available_comps = [c for c, s in manifest.components.items() if s == "included"]
    comp_choices = [
        questionary.Choice(f"{c.capitalize()} ({c})", value=c, checked=True)
        for c in available_comps
    ]
    chosen_comps = questionary.checkbox(
        "Select components to restore:", choices=comp_choices
    ).ask()
    if not chosen_comps:
        click.echo("Restore cancelled: no components selected.")
        return

    click.secho(
        "\nWARNING: Restoring will overwrite selected live configuration, data, and database records!",
        fg="yellow",
        bold=True,
    )
    if not questionary.confirm(
        "Are you sure you want to proceed with the restore?", default=False
    ).ask():
        click.echo("Restore cancelled.")
        return

    click.echo("\nRestoring application backup...")
    try:
        restore_app_backup(
            selected,
            config_dir=config_dir,
            data_dir=data_dir,
            db_url=db_url,
            components=set(chosen_comps),
            recovery_key=recovery_key,
        )
        click.secho(
            "\nApplication restore completed successfully!", fg="green", bold=True
        )
        click.echo(
            "You can now safely restart Bedrock Server Manager with 'bsm web start'."
        )
    except ApplicationBackupError as e:
        click.secho(f"\nRestore failed: {e}", fg="red")
    except Exception as e:
        click.secho(f"\nUnexpected error during restore: {e}", fg="red")


def _interactive_inspect(config_dir: str, data_dir: str) -> None:
    selected = _select_archive_prompt(
        config_dir, data_dir, "Select backup archive to inspect:"
    )
    if not selected:
        return

    recovery_key: str | None = None
    try:
        hdr, manifest = inspect_app_backup(selected, config_dir=config_dir)
    except ApplicationBackupError:
        recovery_key = questionary.password(
            "Archive is encrypted. Enter recovery key:"
        ).ask()
        if not recovery_key:
            return
        hdr, manifest = inspect_app_backup(selected, recovery_key=recovery_key)

    _display_manifest(hdr, manifest, selected)


def _interactive_drill(config_dir: str, data_dir: str, db_url: str) -> None:
    selected = _select_archive_prompt(
        config_dir, data_dir, "Select backup archive to run recovery drill:"
    )
    if not selected:
        return

    recovery_key: str | None = None
    try:
        inspect_app_backup(selected, config_dir=config_dir)
    except ApplicationBackupError:
        recovery_key = questionary.password(
            "Archive is encrypted. Enter recovery key:"
        ).ask()
        if not recovery_key:
            return

    click.echo(f"\nExecuting isolated recovery drill on '{selected.name}'...")
    drill = drill_app_backup(
        selected, config_dir, data_dir, db_url, recovery_key=recovery_key
    )
    _display_drill_result(drill)


def _interactive_list(config_dir: str, data_dir: str) -> None:
    default_dir = get_default_backups_dir(config_dir, data_dir)
    backups = list_app_backups([default_dir], config_dir=config_dir)

    if not backups:
        click.echo(f"\nNo application backups found in {default_dir}")
        return

    catalog = AppBackupCatalog(default_dir).load().get("archives", {})

    click.echo()
    click.secho(
        f"=== Available Application Backups in {default_dir} ===", fg="cyan", bold=True
    )
    for path, hdr, manifest in backups:
        rec = None
        for r in catalog.values():
            if r.get("filename") == path.name:
                rec = r
                break

        drill_str = "Unverified"
        if rec and rec.get("drill"):
            drill_status = rec["drill"].get("status")
            drill_str = (
                click.style("Passed", fg="green")
                if drill_status == "passed"
                else click.style("Failed", fg="red")
            )

        enc_str = (
            click.style(f"Encrypted ({hdr.key_id})", fg="green")
            if hdr.encrypted
            else "Plaintext"
        )
        size_str = _format_size(path.stat().st_size)
        created_str = (
            manifest.created_at.isoformat()[:19].replace("T", " ")
            if manifest and hasattr(manifest.created_at, "isoformat")
            else "Unknown"
        )

        click.echo(f"  - {click.style(path.name, bold=True)}")
        click.echo(
            f"      Created: {created_str} | Size: {size_str} | {enc_str} | Drill: {drill_str}"
        )
    click.echo()


# =========================================================================
# Click Command Group and Subcommands
# =========================================================================


@click.group(invoke_without_command=True)
@click.pass_context
def backup(ctx: click.Context):
    """Manage offline application backups for Bedrock Server Manager."""
    if ctx.invoked_subcommand is None:
        interactive_backup_menu(ctx)


@backup.command("create")
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=True, file_okay=True, path_type=Path),
    help="Output file path or destination directory for the archive.",
)
@click.option(
    "--components",
    "-c",
    type=str,
    help="Comma-separated components to include (database,config,credentials,plugins,data).",
)
@click.option(
    "--encrypt/--no-encrypt",
    default=True,
    help="Encrypt archive using the host keyring.",
)
@click.option(
    "--recovery-key",
    type=str,
    help="Custom encryption password / recovery key.",
)
@click.pass_context
def create_backup_cmd(
    ctx: click.Context,
    output: Path | None,
    components: str | None,
    encrypt: bool,
    recovery_key: str | None,
):
    """Create an application-level backup archive while BSM is offline."""
    config_dir, data_dir, db_url = _resolve_context_paths(ctx)
    selected_components: set[AppComponent] | None = None
    if components:
        selected_components = {c.strip() for c in components.split(",")}  # type: ignore[misc]

    click.echo("Creating application backup...")
    try:
        final_archive, manifest = create_app_backup(
            config_dir=config_dir,
            data_dir=data_dir,
            db_url=db_url,
            output_path=output,
            components=selected_components,
            encrypt=encrypt,
            recovery_key=recovery_key,
        )
        click.secho(
            f"Application backup successful! Saved to: {final_archive}", fg="green"
        )
        hdr, _ = inspect_app_backup(
            final_archive, config_dir=config_dir, recovery_key=recovery_key
        )
        _display_manifest(hdr, manifest, final_archive)
    except ApplicationBackupError as e:
        click.secho(f"Backup failed: {e}", fg="red", err=True)
        raise click.Abort()


@backup.command("restore")
@click.argument("archive", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--components",
    "-c",
    type=str,
    help="Comma-separated components to restore (database,config,credentials,plugins,data).",
)
@click.option(
    "--recovery-key",
    type=str,
    help="Recovery key for decrypting the backup.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt and immediately restore.",
)
@click.pass_context
def restore_backup_cmd(
    ctx: click.Context,
    archive: Path,
    components: str | None,
    recovery_key: str | None,
    yes: bool,
):
    """Restore an application-level backup archive while BSM is offline."""
    config_dir, data_dir, db_url = _resolve_context_paths(ctx)
    try:
        assert_bsm_offline(config_dir, data_dir, db_url)
        hdr, manifest = inspect_app_backup(
            archive, config_dir=config_dir, recovery_key=recovery_key
        )
        _display_manifest(hdr, manifest, archive)

        selected_components: set[AppComponent] | None = None
        if components:
            selected_components = {c.strip() for c in components.split(",")}  # type: ignore[misc]

        if not yes:
            click.secho(
                "WARNING: Restoring will overwrite existing configuration, plugins, data, and database records!",
                fg="yellow",
                bold=True,
            )
            if not click.confirm(
                "Are you sure you want to proceed with the restore?", default=False
            ):
                click.echo("Restore cancelled.")
                return

        click.echo("Restoring application backup...")
        restore_app_backup(
            archive,
            config_dir,
            data_dir,
            db_url,
            components=selected_components,
            recovery_key=recovery_key,
        )
        click.secho(
            "Application restore completed successfully!", fg="green", bold=True
        )
    except ApplicationBackupError as e:
        click.secho(f"Restore failed: {e}", fg="red", err=True)
        raise click.Abort()


@backup.command("inspect")
@click.argument("archive", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--recovery-key",
    type=str,
    help="Recovery key for decrypting the backup.",
)
@click.pass_context
def inspect_backup_cmd(ctx: click.Context, archive: Path, recovery_key: str | None):
    """Inspect and display manifest metadata and encryption headers from a backup archive."""
    config_dir, _, _ = _resolve_context_paths(ctx)
    try:
        hdr, manifest = inspect_app_backup(
            archive, config_dir=config_dir, recovery_key=recovery_key
        )
        _display_manifest(hdr, manifest, archive)
    except ApplicationBackupError as e:
        click.secho(f"Inspection failed: {e}", fg="red", err=True)
        raise click.Abort()


@backup.command("drill")
@click.argument("archive", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--recovery-key",
    type=str,
    help="Recovery key for decrypting the backup.",
)
@click.pass_context
def drill_backup_cmd(ctx: click.Context, archive: Path, recovery_key: str | None):
    """Execute an isolated recovery drill testing archive decryption, hash integrity, and syntax."""
    config_dir, data_dir, db_url = _resolve_context_paths(ctx)
    click.echo(f"Executing isolated recovery drill on '{archive.name}'...")
    try:
        drill = drill_app_backup(
            archive, config_dir, data_dir, db_url, recovery_key=recovery_key
        )
        _display_drill_result(drill)
        if drill.status != "passed":
            raise click.Abort()
    except ApplicationBackupError as e:
        click.secho(f"Drill failed: {e}", fg="red", err=True)
        raise click.Abort()


@backup.command("list")
@click.option(
    "--dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Custom directory to search for application backups.",
)
@click.pass_context
def list_backups_cmd(ctx: click.Context, dir: Path | None):
    """List available application backups in the backup directory with drill and encryption status."""
    config_dir, data_dir, _ = _resolve_context_paths(ctx)
    search_dir = dir or get_default_backups_dir(config_dir, data_dir)
    backups = list_app_backups([search_dir], config_dir=config_dir)

    if not backups:
        click.echo(f"No application backups found in {search_dir}")
        return

    catalog = AppBackupCatalog(search_dir).load().get("archives", {})

    click.echo()
    click.secho(f"Available Application Backups in {search_dir}:", fg="cyan", bold=True)
    for path, hdr, manifest in backups:
        rec = None
        for r in catalog.values():
            if r.get("filename") == path.name:
                rec = r
                break

        drill_str = "Unverified"
        if rec and rec.get("drill"):
            drill_status = rec["drill"].get("status")
            drill_str = (
                click.style("Passed", fg="green")
                if drill_status == "passed"
                else click.style("Failed", fg="red")
            )

        enc_str = (
            click.style(f"Encrypted ({hdr.key_id})", fg="green")
            if hdr.encrypted
            else "Plaintext"
        )
        size_str = _format_size(path.stat().st_size)
        created_str = (
            manifest.created_at.isoformat()[:19].replace("T", " ")
            if manifest and hasattr(manifest.created_at, "isoformat")
            else "Unknown"
        )

        click.echo(f"  - {click.style(path.name, bold=True)}")
        click.echo(
            f"      Created: {created_str} | Size: {size_str} | {enc_str} | Drill: {drill_str}"
        )
    click.echo()


def _recovery_password_prompt(enabled: bool) -> str | None:
    return click.prompt("Recovery key", hide_input=True) if enabled else None


@backup.command("extract")
@click.argument("archive", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("destination", type=click.Path(path_type=Path))
@click.option(
    "--recovery-key",
    is_flag=True,
    help="Prompt privately for the recovery key; do not put it in shell history.",
)
def extract_backup_cmd(archive: Path, destination: Path, recovery_key: bool):
    """Validate and extract a backup archive directly into a new DESTINATION directory."""
    import os
    import tempfile

    from ..backups.archive import unpack
    from ..backups.credentials import private_directory
    from ..error import BSMError

    if destination.exists():
        raise click.ClickException("Destination must not already exist.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(
            prefix=".bsm-extract-", dir=destination.parent
        ) as directory:
            contents = private_directory(Path(directory) / "contents")
            key_val = _recovery_password_prompt(recovery_key)
            manifest = unpack(archive, contents, key_val)
            (contents / "manifest.json").write_text(
                manifest.model_dump_json(indent=2), encoding="utf-8"
            )
            os.replace(contents, destination)
        click.echo(f"Validated backup extracted to {destination}.")
    except BSMError as error:
        raise click.ClickException(str(error)) from error
