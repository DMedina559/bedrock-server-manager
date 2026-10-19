"""Archive validation and offline recovery exercise the actual portable format."""

import io
import tarfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from bedrock_server_manager.__main__ import create_cli_app
from bedrock_server_manager.backups.archive import safe_name
from bedrock_server_manager.error import BackupRestoreError
from bedrock_server_manager.plugins.files import read_plugin_json, write_plugin_json


@pytest.mark.parametrize(
    "name",
    [
        "../escape",
        "/absolute",
        "C:/absolute",
        "world\\escape",
        "world/CON.txt",
        "world/thing.",
        "world/a:b",
        "world//file",
        "world/./file",
    ],
)
def test_portable_paths_reject_unsafe_names(name):
    with pytest.raises(BackupRestoreError):
        safe_name(name)


async def test_offline_encrypted_extraction_requires_no_database(
    populated_server, tmp_path
):
    key = populated_server.backups.credentials.rotate()
    snapshot = await populated_server.backups.create_snapshot(encrypted=True)
    source = Path(populated_server.backups.server_backup_directory) / snapshot.filename
    destination = tmp_path / "offline"
    result = CliRunner().invoke(
        create_cli_app(),
        [
            "--db-url",
            "unavailable://",
            "backup",
            "extract",
            str(source),
            str(destination),
            "--recovery-key",
        ],
        input=key.secret.get_secret_value() + "\n",
    )
    assert result.exit_code == 0, result.output
    assert (destination / "world" / "level.dat").exists()
    assert (destination / "manifest.json").exists()
    assert not (destination / "credentials").exists()


async def test_corrupt_encrypted_backup_does_not_restore(populated_server):
    server = populated_server
    server.backups.credentials.rotate()
    snapshot = await server.backups.create_snapshot(encrypted=True)
    path = Path(server.backups.server_backup_directory) / snapshot.filename
    with tarfile.open(path) as source:
        first, payload = source.getmembers()
        metadata = source.extractfile(first).read()
        content = bytearray(source.extractfile(payload).read())
    content[-1] ^= 1
    with tarfile.open(path, "w") as archive:
        first.size = len(metadata)
        archive.addfile(first, io.BytesIO(metadata))
        payload.size = len(content)
        archive.addfile(payload, io.BytesIO(content))
    properties = Path(server.paths.server_properties_path).read_bytes()
    with pytest.raises(BackupRestoreError):
        await server.backups.plan_restore(snapshot.backup_id, ["server.properties"])
    assert Path(server.paths.server_properties_path).read_bytes() == properties


async def test_archive_inventory_rejects_extra_file(populated_server):

    server = populated_server
    snapshot = await server.backups.create_snapshot()
    path = Path(server.backups.server_backup_directory) / snapshot.filename
    with tarfile.open(path) as outer:
        metadata = outer.extractfile("bsm.json").read()
        compressed = outer.extractfile("payload.tar.gz").read()
    output = io.BytesIO()
    with (
        tarfile.open(fileobj=io.BytesIO(compressed), mode="r:gz") as source,
        tarfile.open(fileobj=output, mode="w:gz") as target,
    ):
        for member in source:
            target.addfile(
                member, source.extractfile(member) if member.isfile() else None
            )
        extra = tarfile.TarInfo("server-config/undeclared-secret")
        extra.size = 1
        target.addfile(extra, io.BytesIO(b"x"))
    with tarfile.open(path, "w") as outer:
        for name, content in (
            ("bsm.json", metadata),
            ("payload.tar.gz", output.getvalue()),
        ):
            member = tarfile.TarInfo(name)
            member.size = len(content)
            outer.addfile(member, io.BytesIO(content))
    with pytest.raises(BackupRestoreError):
        await server.backups.inspect_snapshot(snapshot.backup_id)


def test_plugin_files_are_owner_scoped(tmp_path):
    write_plugin_json(str(tmp_path), "first", "settings.json", {"value": 1})
    assert read_plugin_json(str(tmp_path), "first", "settings.json") == {"value": 1}
    with pytest.raises(BackupRestoreError):
        read_plugin_json(str(tmp_path), "first", "../second/settings.json")
    with pytest.raises(BackupRestoreError):
        read_plugin_json(
            str(tmp_path), "first", "../../../credentials/backup-keys.json"
        )
