import importlib
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from bedrock_server_manager.cli.cleanup import _cleanup_pycache, cleanup
from bedrock_server_manager.cli.logs import logs
from bedrock_server_manager.state.models import PluginInfoState, ServerConfigState


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def cache_root(tmp_path, monkeypatch):
    module = importlib.import_module("bedrock_server_manager.cli.cleanup")
    script = tmp_path / "bedrock_server_manager" / "cli" / "cleanup.py"
    script.parent.mkdir(parents=True)
    script.write_text("# isolated package location\n")
    monkeypatch.setattr(module, "__file__", str(script))
    return tmp_path / "bedrock_server_manager"


def test_cleanup_no_options(runner, app_context):
    result = runner.invoke(cleanup, obj={"app_context": app_context})
    assert result.exit_code == 0
    assert "No cleanup options specified" in result.output


@pytest.mark.parametrize("count", [0, 3])
def test_cleanup_cache(runner, app_context, cache_root, count):
    caches = []
    for i in range(count):
        path = cache_root / f"package_{i}" / "__pycache__"
        path.mkdir(parents=True)
        (path / "module.pyc").write_bytes(b"cached bytecode")
        caches.append(path)
    source = cache_root / "keep.py"
    source.write_text("retained source")
    result = runner.invoke(cleanup, ["--cache"], obj={"app_context": app_context})
    assert result.exit_code == 0, result.output
    expected = (
        f"Cleaned up {count} __pycache__ director(ies)"
        if count
        else "No __pycache__ directories found to clean"
    )
    assert expected in result.output
    assert all(not path.exists() for path in caches)
    assert source.read_text() == "retained source"
    assert not list(cache_root.rglob("__pycache__"))


@pytest.mark.parametrize("override", [False, True])
@pytest.mark.parametrize("count", [0, 1, 4])
def test_cleanup_logs(runner, app_context, tmp_path, override, count):
    configured = Path(app_context.log_dir)
    configured.mkdir(parents=True, exist_ok=True)
    directory = tmp_path / "override" if override else configured
    directory.mkdir(exist_ok=True)
    untouched = configured / "other.log.0"
    if override:
        untouched.write_text("other directory")
    for i in range(count):
        path = directory / f"app.log.{i}"
        path.write_text(f"log {i}")
        os.utime(path, (1000000000 + i, 1000000000 + i))
    (directory / "notes.txt").write_text("keep")
    (directory / "current.log").write_text("active log")
    args = ["--logs"] + (["--log-dir", str(directory)] if override else [])
    result = runner.invoke(cleanup, args, obj={"app_context": app_context})
    assert result.exit_code == 0, result.output
    expected = {f"app.log.{count - 1}"} if count else set()
    assert {p.name for p in directory.glob("*.log.*")} == expected
    assert (directory / "notes.txt").read_text() == "keep"
    assert (directory / "current.log").read_text() == "active log"
    if count > 1:
        assert f"Cleaned up {count - 1} log file(s)" in result.output
    else:
        assert "No log files found to clean" in result.output
    if override:
        assert untouched.read_text() == "other directory"


def test_cleanup_logs_missing_dir(runner, app_context, monkeypatch):
    monkeypatch.setattr("bedrock_server_manager.context.AppContext.log_dir", None)
    result = runner.invoke(cleanup, ["--logs"], obj={"app_context": app_context})
    assert result.exit_code == 1
    assert "Log directory not specified" in result.output


def test_internal_cleanup_pycache_error(cache_root, monkeypatch):
    def fail_scan(*args, **kwargs):
        raise OSError("Injected directory scan failure")

    monkeypatch.setattr(Path, "rglob", fail_scan)
    from bedrock_server_manager.error import FileOperationError

    with pytest.raises(FileOperationError):
        _cleanup_pycache()


def test_cleanup_orphans_and_dry_run(runner, app_context):
    # 1. Seed orphaned plugin DB entry and private plugin dir
    app_context.state.plugins.set(
        PluginInfoState(plugin_name="ghost_plugin", enabled=True)
    )
    ghost_plugin_dir = Path(app_context.config_dir) / "plugins" / "ghost_plugin"
    ghost_plugin_dir.mkdir(parents=True, exist_ok=True)
    (ghost_plugin_dir / "state.json").write_text("{}")

    public_dir = Path(app_context.config_dir) / "plugins" / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    (public_dir / "shared.txt").write_text("keep")

    # 2. Seed orphaned server DB entry, runtime dir, log dir, and stale PID file
    app_context.state.servers.set(
        ServerConfigState(server_name="ghost_server", status="STOPPED")
    )
    ghost_runtime_dir = (
        Path(app_context.config_dir) / "runtime" / "servers" / "ghost_server"
    )
    ghost_runtime_dir.mkdir(parents=True, exist_ok=True)
    ghost_log_dir = Path(app_context.config_dir) / "logs" / "servers" / "ghost_server"
    ghost_log_dir.mkdir(parents=True, exist_ok=True)
    stale_web_pid = Path(app_context.config_dir) / "runtime" / "web_server.pid"
    stale_web_pid.parent.mkdir(parents=True, exist_ok=True)
    stale_web_pid.write_text("99999999")

    # Dry run preserves everything
    dry_res = runner.invoke(
        cleanup, ["--orphans", "--dry-run"], obj={"app_context": app_context}
    )
    assert dry_res.exit_code == 0, dry_res.output
    assert "Would clean up" in dry_res.output
    assert "ghost_plugin" in app_context.state.plugins.plugins
    assert ghost_plugin_dir.exists()
    assert ghost_runtime_dir.exists()
    assert ghost_log_dir.exists()
    assert stale_web_pid.exists()

    # Real run removes orphans and stale PID files while keeping public dir
    res = runner.invoke(cleanup, ["--orphans"], obj={"app_context": app_context})
    assert res.exit_code == 0, res.output
    assert "ghost_plugin" not in app_context.state.plugins.plugins
    assert not ghost_plugin_dir.exists()
    assert (public_dir / "shared.txt").read_text() == "keep"
    assert "ghost_server" not in app_context.state.servers.servers
    assert not ghost_runtime_dir.exists()
    assert not ghost_log_dir.exists()
    assert not stale_web_pid.exists()


def test_logs_cli_list_and_view(runner, app_context, real_bedrock_server, monkeypatch):
    log_dir = Path(app_context.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    app_log = log_dir / "bedrock_server_manager_20261101_120000_000000_4242_abc.log"
    app_log.write_text("app line 1\napp line 2\napp line 3\n", encoding="utf-8")

    # Simulate short-lived CLI invocation log with current PID — should be excluded
    cli_log = (
        log_dir / f"bedrock_server_manager_20261101_120500_000000_{os.getpid()}_cli.log"
    )
    cli_log.write_text("cli invocation log\n", encoding="utf-8")

    server_log_dir = Path(real_bedrock_server.paths.server_log_dir)
    server_log_dir.mkdir(parents=True, exist_ok=True)
    s_log = (
        server_log_dir
        / f"{real_bedrock_server.server_name}_20261101_120000_000000_5151_def.log"
    )
    s_log.write_text("server line 1\nserver line 2\n", encoding="utf-8")

    # Without verified running processes, newest non-CLI logs are marked [LATEST]
    list_res = runner.invoke(logs, ["--list"], obj={"app_context": app_context})
    assert list_res.exit_code == 0, list_res.output
    assert app_log.name in list_res.output
    assert cli_log.name not in list_res.output
    assert s_log.name in list_res.output
    assert "[LATEST]" in list_res.output
    assert "[ACTIVE" not in list_res.output

    # With verified running web & server PIDs, matching PID logs are marked [ACTIVE - PID ...]
    from types import SimpleNamespace

    async def _fake_web_proc(ctx):
        return SimpleNamespace(pid=4242)

    async def _fake_server_procs(ctx, names):
        return {real_bedrock_server.server_name: SimpleNamespace(pid=5151)}

    monkeypatch.setattr(
        "bedrock_server_manager.cli.logs.get_verified_web_process",
        _fake_web_proc,
    )
    monkeypatch.setattr(
        "bedrock_server_manager.cli.logs.get_verified_server_processes",
        _fake_server_procs,
    )
    active_list_res = runner.invoke(logs, ["--list"], obj={"app_context": app_context})
    assert active_list_res.exit_code == 0, active_list_res.output
    assert "[ACTIVE - PID 4242]" in active_list_res.output
    assert "[ACTIVE - PID 5151]" in active_list_res.output

    app_res = runner.invoke(
        logs, ["--app", "-n", "2"], obj={"app_context": app_context}
    )
    assert app_res.exit_code == 0, app_res.output
    assert "app line 1" not in app_res.output
    assert "app line 2\napp line 3" in app_res.output

    srv_res = runner.invoke(
        logs,
        ["--server", real_bedrock_server.server_name, "-n", "1"],
        obj={"app_context": app_context},
    )
    assert srv_res.exit_code == 0, srv_res.output
    assert "server line 1" not in srv_res.output
    assert "server line 2" in srv_res.output


@pytest.mark.parametrize("target", ["servers", "plugins"])
@pytest.mark.parametrize("failure", ["missing", "unreadable", "partial"])
async def test_cleanup_preserves_data_when_inventory_unavailable(
    app_context, tmp_path, monkeypatch, target, failure
):
    from bedrock_server_manager.cli.cleanup import (
        _cleanup_orphaned_plugins_async,
        _cleanup_orphaned_servers_async,
    )

    app_context.state.servers.set(ServerConfigState(server_name="kept"))
    app_context.state.plugins.set(PluginInfoState(plugin_name="kept", enabled=True))
    directory = Path(app_context.config_dir) / (
        "runtime/servers/kept" if target == "servers" else "plugins/kept"
    )
    directory.mkdir(parents=True, exist_ok=True)
    marker = directory / "important.txt"
    marker.write_text("retained")
    source = tmp_path / "inventory"
    app_context.state.settings.set(f"paths.{target}", str(source))
    if failure != "missing":
        source.mkdir()
        original = Path.iterdir

        def fail_scan(path):
            if path == source:
                if failure == "partial":
                    child = source / "seen"
                    child.mkdir(exist_ok=True)
                    yield child
                raise PermissionError("Inventory unavailable")
            yield from original(path)

        monkeypatch.setattr(Path, "iterdir", fail_scan)
    cleanup_fn = (
        _cleanup_orphaned_servers_async
        if target == "servers"
        else _cleanup_orphaned_plugins_async
    )
    for dry_run in (True, False):
        result = await cleanup_fn(app_context, dry_run=dry_run)
        assert f"inventory:{target}" in result.failures
        assert not result.deleted
        assert marker.read_text() == "retained"
        assert "kept" in app_context.state.servers.servers
        assert "kept" in app_context.state.plugins.plugins


@pytest.mark.parametrize("target", ["servers", "plugins"])
async def test_cleanup_commit_failure_preserves_state_dirty_flags_and_files(
    app_context, monkeypatch, target
):
    from contextlib import asynccontextmanager

    from bedrock_server_manager.cli.cleanup import (
        _cleanup_orphaned_plugins_async,
        _cleanup_orphaned_servers_async,
    )

    # Persist an orphan in both the DB and state so rollback is checked end to end.
    plugin = PluginInfoState(plugin_name="ghost", enabled=True)
    server = ServerConfigState(server_name="ghost", custom={"ghost": {"x": 1}})
    app_context.state.plugins.set(plugin)
    app_context.state.servers.set(server)
    app_context.state.settings.set("plugin_settings", {"ghost": {"x": 1}})
    app_context.state.settings.set("custom", {"ghost": {"x": 1}})
    async with app_context.storage.transaction() as session:
        await app_context.storage.plugin_repo.save_plugin(session, plugin)
        await app_context.storage.server_repo.save_server(session, server)
        await app_context.storage.settings_repo.save_settings(
            session, app_context.state.settings.to_dict()
        )
    for key in ("servers", "plugins"):
        Path(app_context.settings.get(f"paths.{key}")).mkdir(
            parents=True, exist_ok=True
        )
    dirs = [
        Path(app_context.config_dir) / suffix
        for suffix in ("runtime/servers/ghost", "logs/servers/ghost", "plugins/ghost")
    ]
    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "important.txt").write_text("retained")
    before_settings = app_context.state.settings.model_dump()
    dirty_servers = app_context.state.servers.dirty_keys
    dirty_plugins = app_context.state.plugins.dirty_keys
    dirty_settings = app_context.state.settings.dirty_keys
    original = app_context.storage.transaction

    @asynccontextmanager
    async def failed_transaction():
        async with original() as session:
            yield session
            raise RuntimeError("Injected commit failure")

    cleanup_fn = (
        _cleanup_orphaned_servers_async
        if target == "servers"
        else _cleanup_orphaned_plugins_async
    )
    with monkeypatch.context() as scoped:
        scoped.setattr(app_context.storage, "transaction", failed_transaction)
        result = await cleanup_fn(app_context)
    assert f"db:{target}" in result.failures
    assert not result.deleted
    assert app_context.state.servers.get("ghost") == server
    assert app_context.state.plugins.get("ghost") == plugin
    assert app_context.state.settings.model_dump() == before_settings
    assert app_context.state.servers.dirty_keys == dirty_servers
    assert app_context.state.plugins.dirty_keys == dirty_plugins
    assert app_context.state.settings.dirty_keys == dirty_settings
    assert all(
        (directory / "important.txt").read_text() == "retained" for directory in dirs
    )
    async with original() as session:
        assert await app_context.storage.server_repo.get_server_by_name(
            session, "ghost"
        )
        assert any(
            item.plugin_name == "ghost"
            for item in await app_context.storage.plugin_repo.get_all_plugins(session)
        )
        persisted = await app_context.storage.settings_repo.get_all_settings(session)
        assert persisted["plugin_settings"]["ghost"] == {"x": 1}
        assert persisted["custom"]["ghost"] == {"x": 1}


async def test_plugin_cleanup_commits_all_scopes_before_publishing(
    app_context, monkeypatch
):
    from bedrock_server_manager.cli.cleanup import _cleanup_orphaned_plugins_async

    module = importlib.import_module("bedrock_server_manager.cli.cleanup")
    monkeypatch.setattr(module, "_discover_installed_plugin_names", lambda _: {"keep"})
    for name in ("ghost", "keep"):
        app_context.state.plugins.set(PluginInfoState(plugin_name=name, enabled=True))
        directory = Path(app_context.config_dir) / "plugins" / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "state.json").write_text("retained")
    values = {"ghost": {"value": 1}, "keep": {"value": 2}}
    app_context.state.settings.set("plugin_settings", values)
    app_context.state.settings.set("custom", values)
    app_context.state.servers.set(
        ServerConfigState(server_name="server", custom=values)
    )
    await app_context.storage.flush(app_context.state)
    original = app_context.storage.transaction
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def observe_commit():
        async with original() as session:
            yield session
            assert "ghost" in app_context.state.plugins.plugins
            assert app_context.state.settings.custom == values
            assert app_context.state.servers.get("server").custom == values
            assert (Path(app_context.config_dir) / "plugins/ghost/state.json").exists()

    with monkeypatch.context() as scoped:
        scoped.setattr(app_context.storage, "transaction", observe_commit)
        result = await _cleanup_orphaned_plugins_async(app_context)
    assert not result.failures
    assert "ghost" not in app_context.state.plugins.plugins
    expected = {"keep": {"value": 2}}
    assert app_context.state.settings.plugin_settings == expected
    assert app_context.state.settings.custom == expected
    assert app_context.state.servers.get("server").custom == expected
    assert not (Path(app_context.config_dir) / "plugins/ghost").exists()
    assert (Path(app_context.config_dir) / "plugins/keep/state.json").exists()
    async with original() as session:
        settings = await app_context.storage.settings_repo.get_all_settings(session)
        assert settings["custom"] == expected
        assert settings["plugin_settings"] == expected
        server = await app_context.storage.server_repo.get_server_by_name(
            session, "server"
        )
        assert server.custom == expected
        plugins = await app_context.storage.plugin_repo.get_all_plugins(session)
        assert {plugin.plugin_name for plugin in plugins} == {"keep"}
