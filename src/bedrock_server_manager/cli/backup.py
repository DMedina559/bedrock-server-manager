"""Offline portable backup inspection and recovery without an application database."""

import tempfile
from pathlib import Path

import click

from ..backups.archive import unpack
from ..backups.credentials import private_directory
from ..error import BSMError


@click.group()
def backup():
    """Inspect or extract a portable server backup offline."""


def recovery_password(enabled: bool) -> str | None:
    return click.prompt("Recovery key", hide_input=True) if enabled else None


@backup.command("inspect")
@click.argument("archive", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--recovery-key",
    is_flag=True,
    help="Prompt privately for an encrypted backup's key.",
)
def inspect_backup(archive: Path, recovery_key: bool):
    """Validate ARCHIVE and display its manifest without extracting live data."""
    try:
        with tempfile.TemporaryDirectory(prefix="bsm-inspect-") as directory:
            manifest = unpack(archive, Path(directory), recovery_password(recovery_key))
        click.echo(manifest.model_dump_json(indent=2))
    except BSMError as error:
        raise click.ClickException(str(error)) from error


@backup.command("extract")
@click.argument("archive", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("destination", type=click.Path(path_type=Path))
@click.option(
    "--recovery-key",
    is_flag=True,
    help="Prompt privately for the recovery key; do not put it in shell history.",
)
def extract_backup(archive: Path, destination: Path, recovery_key: bool):
    """Validate ARCHIVE and extract into a new DESTINATION directory."""
    import os

    if destination.exists():
        raise click.ClickException("Destination must not already exist.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(
            prefix=".bsm-extract-", dir=destination.parent
        ) as directory:
            contents = private_directory(Path(directory) / "contents")
            manifest = unpack(archive, contents, recovery_password(recovery_key))
            (contents / "manifest.json").write_text(
                manifest.model_dump_json(indent=2), encoding="utf-8"
            )
            os.replace(contents, destination)
        click.echo(f"Validated backup extracted to {destination}.")
    except BSMError as error:
        raise click.ClickException(str(error)) from error
