from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from bedrock_server_manager.cli.backup import backup
from bedrock_server_manager.utils.threads import run_in_thread


@pytest.fixture
def invoke_backup(app_context):
    async def invoke(*arguments):
        return await run_in_thread(
            CliRunner().invoke,
            backup,
            list(arguments),
            obj={
                "config_dir": app_context.config_dir,
                "data_dir": app_context.data_dir,
                "db_url": app_context.db_url,
            },
        )

    return invoke


async def test_backup_offline_guard_blocks_when_running(
    invoke_backup, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "bedrock_server_manager.backups.app.check_bsm_offline",
        lambda *args, **kwargs: (False, 9999),
    )
    result = await invoke_backup("create")
    assert result.exit_code != 0
    assert "Bedrock Server Manager is currently running" in result.output

    fake_file = tmp_path / "fake.bsmappbackup"
    fake_file.write_text("dummy")
    restore_res = await invoke_backup("restore", str(fake_file), "--yes")
    assert restore_res.exit_code != 0
    assert "Bedrock Server Manager is currently running" in restore_res.output


async def test_backup_create_inspect_list_restore_round_trip(
    invoke_backup, app_context, tmp_path
):
    # Setup test file in config
    cfg_file = Path(app_context.config_dir) / "test_config.json"
    cfg_file.write_text('{"app_test": 123}', encoding="utf-8")

    archive_path = tmp_path / "test_app_backup.bsmappbackup"

    # 1. Create unencrypted backup
    create_result = await invoke_backup(
        "create", "--output", str(archive_path), "--no-encrypt"
    )
    assert create_result.exit_code == 0, create_result.output
    assert archive_path.is_file()
    assert "Application backup successful!" in create_result.output

    # 2. Inspect backup
    inspect_result = await invoke_backup("inspect", str(archive_path))
    assert inspect_result.exit_code == 0, inspect_result.output
    assert "bsmappbackup" in inspect_result.output
    assert "Components Included:" in inspect_result.output

    # 3. List backups
    list_result = await invoke_backup("list", "--dir", str(tmp_path))
    assert list_result.exit_code == 0, list_result.output
    assert archive_path.name in list_result.output

    # 4. Modify config file, then restore
    cfg_file.write_text('{"app_test": 999}', encoding="utf-8")
    assert cfg_file.read_text(encoding="utf-8") == '{"app_test": 999}'

    restore_result = await invoke_backup("restore", str(archive_path), "--yes")
    assert restore_result.exit_code == 0, restore_result.output
    assert "Application restore completed successfully!" in restore_result.output

    # Verify restored content
    assert cfg_file.read_text(encoding="utf-8") == '{"app_test": 123}'


async def test_backup_encryption_and_drill(invoke_backup, app_context, tmp_path):
    archive_path = tmp_path / "encrypted_backup.bsmappbackup"
    key = "TestRecoveryKey123!Safe"

    # 1. Create with encryption
    create_result = await invoke_backup(
        "create",
        "--output",
        str(archive_path),
        "--recovery-key",
        key,
    )
    assert create_result.exit_code == 0, create_result.output
    assert archive_path.is_file()

    # 2. Inspect with wrong/missing key should fail
    fail_inspect = await invoke_backup("inspect", str(archive_path))
    assert fail_inspect.exit_code != 0
    assert "requires a recovery key" in fail_inspect.output

    # 3. Inspect with recovery key succeeds
    ok_inspect = await invoke_backup(
        "inspect", str(archive_path), "--recovery-key", key
    )
    assert ok_inspect.exit_code == 0, ok_inspect.output
    assert "Encrypted" in ok_inspect.output

    # 4. Run recovery drill
    drill_result = await invoke_backup(
        "drill", str(archive_path), "--recovery-key", key
    )
    assert drill_result.exit_code == 0, drill_result.output
    assert "PASSED" in drill_result.output
    assert "Checked Files:" in drill_result.output

    # 5. List shows encrypted and passed drill
    list_result = await invoke_backup("list", "--dir", str(tmp_path))
    assert list_result.exit_code == 0, list_result.output
    assert "Passed" in list_result.output
    assert "Encrypted" in list_result.output


async def test_backup_selective_component_restore(invoke_backup, app_context, tmp_path):
    cfg_file = Path(app_context.config_dir) / "selective_config.json"
    cfg_file.write_text('{"selected": "initial"}', encoding="utf-8")

    archive_path = tmp_path / "selective_backup.bsmappbackup"
    res = await invoke_backup("create", "-o", str(archive_path), "--no-encrypt")
    assert res.exit_code == 0, res.output

    # Modify config
    cfg_file.write_text('{"selected": "modified"}', encoding="utf-8")

    # Restore only config component
    restore_res = await invoke_backup(
        "restore", str(archive_path), "--components", "config", "--yes"
    )
    assert restore_res.exit_code == 0, restore_res.output
    assert cfg_file.read_text(encoding="utf-8") == '{"selected": "initial"}'


async def test_backup_interactive_menu_exit(invoke_backup, monkeypatch):
    monkeypatch.setattr(
        "questionary.select",
        lambda *args, **kwargs: SimpleNamespace(ask=lambda: "exit"),
    )
    result = await invoke_backup()
    assert result.exit_code == 0
    assert "Bedrock Server Manager - Offline Application Backup" in result.output


async def test_backup_interactive_create_flow(
    invoke_backup, app_context, tmp_path, monkeypatch
):
    archive_path = tmp_path / "interactive_backup.bsmappbackup"
    actions = ["create"]

    monkeypatch.setattr(
        "questionary.select",
        lambda *args, **kwargs: SimpleNamespace(ask=lambda: actions.pop(0)),
    )
    monkeypatch.setattr(
        "questionary.text",
        lambda *args, **kwargs: SimpleNamespace(ask=lambda: str(archive_path)),
    )
    monkeypatch.setattr(
        "questionary.checkbox",
        lambda *args, **kwargs: SimpleNamespace(ask=lambda: ["config", "database"]),
    )
    monkeypatch.setattr(
        "questionary.confirm",
        lambda *args, **kwargs: SimpleNamespace(ask=lambda: False),
    )

    result = await invoke_backup()
    assert result.exit_code == 0, result.output
    assert archive_path.is_file()
    assert "Application backup created successfully!" in result.output


async def test_backup_always_excludes_servers_and_backups(
    invoke_backup, app_context, tmp_path
):
    # Setup dummy server directories in both config_dir and data_dir
    config_servers = Path(app_context.config_dir) / "servers" / "survival"
    config_servers.mkdir(parents=True, exist_ok=True)
    (config_servers / "bedrock_server.exe").write_text("binary", encoding="utf-8")

    config_backups = Path(app_context.config_dir) / "backups"
    config_backups.mkdir(parents=True, exist_ok=True)
    (config_backups / "world_snapshot.tar.gz").write_text("archive", encoding="utf-8")

    data_servers = Path(app_context.data_dir) / "servers" / "creative"
    data_servers.mkdir(parents=True, exist_ok=True)
    (data_servers / "server.properties").write_text("motd=test", encoding="utf-8")

    data_backups = Path(app_context.data_dir) / "backups"
    data_backups.mkdir(parents=True, exist_ok=True)
    (data_backups / "snapshot.tar.gz").write_text("archive", encoding="utf-8")

    archive_path = tmp_path / "app_backup_no_servers.bsmappbackup"
    res = await invoke_backup("create", "-o", str(archive_path), "--no-encrypt")
    assert res.exit_code == 0, res.output

    from bedrock_server_manager.backups.app import inspect_app_backup

    _, manifest = inspect_app_backup(archive_path)
    file_paths = [f.path for f in manifest.files]

    # Verify no server or world backup files are included anywhere in the archive
    assert not any("servers/" in p for p in file_paths)
    assert not any("backups/" in p for p in file_paths)
    assert not any(
        p.endswith("bedrock_server.exe") or p.endswith("/bedrock_server")
        for p in file_paths
    )
    assert not any("server.properties" in p for p in file_paths)


async def test_backup_does_not_duplicate_plugins_or_plugin_data(
    invoke_backup, app_context, tmp_path
):
    # Installed plugin module in data_dir/plugins
    installed_plugins_dir = Path(app_context.data_dir) / "plugins"
    installed_plugins_dir.mkdir(parents=True, exist_ok=True)
    plugin_module = installed_plugins_dir / "custom_plugin.py"
    plugin_module.write_text("# custom plugin code", encoding="utf-8")

    # Plugin runtime data in config_dir/plugins/<plugin_name>/
    plugin_data_dir = Path(app_context.config_dir) / "plugins" / "custom_plugin"
    plugin_data_dir.mkdir(parents=True, exist_ok=True)
    plugin_data_file = plugin_data_dir / "state.json"
    plugin_data_file.write_text('{"counter": 42}', encoding="utf-8")

    archive_path = tmp_path / "dedup_backup.bsmappbackup"
    res = await invoke_backup("create", "-o", str(archive_path), "--no-encrypt")
    assert res.exit_code == 0, res.output

    from bedrock_server_manager.backups.app import inspect_app_backup

    _, manifest = inspect_app_backup(archive_path)
    file_paths = [f.path for f in manifest.files]

    # Installed plugin appears only once under plugins/
    assert file_paths.count("plugins/custom_plugin.py") == 1
    assert not any(p.startswith("plugins/plugins/") for p in file_paths)

    # Plugin runtime data appears only once under data/plugins/, never under config/plugins/ or plugins/
    assert file_paths.count("data/plugins/custom_plugin/state.json") == 1
    assert not any(p.startswith("config/plugins/") for p in file_paths)
    assert not any(p.startswith("config/db/") for p in file_paths)

    # Verify round-trip restore puts both back in their respective locations
    plugin_module.unlink()
    plugin_data_file.unlink()

    restore_res = await invoke_backup("restore", str(archive_path), "--yes")
    assert restore_res.exit_code == 0, restore_res.output
    assert plugin_module.read_text(encoding="utf-8") == "# custom plugin code"
    assert plugin_data_file.read_text(encoding="utf-8") == '{"counter": 42}'
