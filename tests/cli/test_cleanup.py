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

    # 2. Seed orphaned server DB entry, runtime dir, and log dir
    app_context.state.servers.set(
        ServerConfigState(server_name="ghost_server", status="STOPPED")
    )
    ghost_runtime_dir = (
        Path(app_context.config_dir) / "runtime" / "servers" / "ghost_server"
    )
    ghost_runtime_dir.mkdir(parents=True, exist_ok=True)
    ghost_log_dir = Path(app_context.config_dir) / "logs" / "servers" / "ghost_server"
    ghost_log_dir.mkdir(parents=True, exist_ok=True)

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

    # Real run removes orphans while keeping public dir
    res = runner.invoke(cleanup, ["--orphans"], obj={"app_context": app_context})
    assert res.exit_code == 0, res.output
    assert "ghost_plugin" not in app_context.state.plugins.plugins
    assert not ghost_plugin_dir.exists()
    assert (public_dir / "shared.txt").read_text() == "keep"
    assert "ghost_server" not in app_context.state.servers.servers
    assert not ghost_runtime_dir.exists()
    assert not ghost_log_dir.exists()


def test_logs_cli_list_and_view(runner, app_context, real_bedrock_server):
    log_dir = Path(app_context.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    app_log = log_dir / "bedrock_server_manager_20261101_120000_000000_1_abc.log"
    app_log.write_text("app line 1\napp line 2\napp line 3\n", encoding="utf-8")

    server_log_dir = Path(real_bedrock_server.paths.server_log_dir)
    server_log_dir.mkdir(parents=True, exist_ok=True)
    s_log = (
        server_log_dir
        / f"{real_bedrock_server.server_name}_20261101_120000_000000_1_def.log"
    )
    s_log.write_text("server line 1\nserver line 2\n", encoding="utf-8")

    list_res = runner.invoke(logs, ["--list"], obj={"app_context": app_context})
    assert list_res.exit_code == 0, list_res.output
    assert app_log.name in list_res.output
    assert s_log.name in list_res.output
    assert "[ACTIVE]" in list_res.output

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
