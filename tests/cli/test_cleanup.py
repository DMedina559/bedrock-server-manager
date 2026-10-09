import importlib
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from bedrock_server_manager.cli.cleanup import _cleanup_pycache, cleanup


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
    return tmp_path


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
    assert _cleanup_pycache() == 0
