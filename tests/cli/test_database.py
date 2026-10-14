import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from bedrock_server_manager.cli.database import database
from bedrock_server_manager.utils.threads import run_in_thread


@pytest.fixture
def invoke_database(app_context):
    async def invoke(*arguments):
        return await run_in_thread(
            CliRunner().invoke,
            database,
            list(arguments),
            obj={"app_context": app_context},
        )

    return invoke


async def test_database_status_reads_actual_migration_revision(invoke_database):
    result = await invoke_database("status")
    assert result.exit_code == 0, result.output
    assert "Database is up to date!" in result.output


async def test_database_upgrade_is_idempotent_and_creates_backup(
    invoke_database, app_context
):
    result = await invoke_database("upgrade", "--yes")
    assert result.exit_code == 0, result.output
    backups = list(
        Path(app_context.settings.get("paths.backups")).glob("db_data_backup_*.json")
    )
    assert backups
    assert json.loads(backups[0].read_text())["_metadata"]["alembic_version"]
    assert (await invoke_database("status")).exit_code == 0


async def test_database_backup_and_restore_round_trip(
    invoke_database, app_context, tmp_path, monkeypatch
):
    await app_context.settings.set("custom.integration", {"saved": True})
    backup = tmp_path / "backup.json"
    result = await invoke_database("backup", "--output", str(backup))
    assert result.exit_code == 0, result.output
    assert json.loads(backup.read_text())["_metadata"]["alembic_version"]
    await app_context.settings.set("custom.integration", {"saved": False})
    monkeypatch.setattr(
        "questionary.confirm", lambda *args, **kwargs: SimpleNamespace(ask=lambda: True)
    )
    result = await invoke_database("restore", "--input", str(backup))
    assert result.exit_code == 0, result.output
    await app_context.settings.reload()
    assert app_context.settings.get("custom.integration") == {"saved": True}


async def test_restore_cancellation_preserves_database(
    invoke_database, app_context, tmp_path, monkeypatch
):
    await app_context.settings.set("custom.integration", "original")
    backup = tmp_path / "backup.json"
    assert (await invoke_database("backup", "--output", str(backup))).exit_code == 0
    monkeypatch.setattr(
        "questionary.confirm",
        lambda *args, **kwargs: SimpleNamespace(ask=lambda: False),
    )
    result = await invoke_database("restore", "--input", str(backup))
    assert result.exit_code == 1
    await app_context.settings.reload()
    assert app_context.settings.get("custom.integration") == "original"


async def test_version_mismatch_rejection_preserves_database(
    invoke_database, app_context, tmp_path, monkeypatch
):
    await app_context.settings.set("custom.integration", "original")
    backup = tmp_path / "backup.json"
    assert (await invoke_database("backup", "--output", str(backup))).exit_code == 0
    data = json.loads(backup.read_text())
    data["_metadata"]["alembic_version"] = "different-version"
    backup.write_text(json.dumps(data))
    decisions = iter([True, False])
    monkeypatch.setattr(
        "questionary.confirm",
        lambda *args, **kwargs: SimpleNamespace(ask=lambda: next(decisions)),
    )
    result = await invoke_database("restore", "--input", str(backup))
    assert result.exit_code == 1
    assert "version mismatch" in result.output
    await app_context.settings.reload()
    assert app_context.settings.get("custom.integration") == "original"


async def test_backup_failure_preserves_original_error(
    invoke_database, tmp_path, caplog
):
    import logging

    with caplog.at_level(logging.ERROR):
        result = await invoke_database("backup", "--output", str(tmp_path))
    assert result.exit_code == 1
    assert "Database backup failed" in result.output
    failures = [
        record
        for record in caplog.records
        if "Database backup failed" in record.getMessage()
    ]
    assert len(failures) == 1
    assert isinstance(failures[0].exc_info[1], OSError)
