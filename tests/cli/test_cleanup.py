from pathlib import Path

import pytest
from click.testing import CliRunner

from bedrock_server_manager.cli.cleanup import (
    _cleanup_log_files,
    _cleanup_pycache,
    cleanup,
)


@pytest.fixture
def runner():
    return CliRunner()


def test_cleanup_no_options(runner, app_context):
    """Test cleanup command warns the user when neither --cache nor --logs is passed."""
    result = runner.invoke(cleanup, obj={"app_context": app_context})
    assert result.exit_code == 0
    assert "No cleanup options specified" in result.output


def test_cleanup_cache(runner, app_context, monkeypatch):
    """Test cleanup command successfully removes mock __pycache__ directories."""
    monkeypatch.setattr(
        "bedrock_server_manager.cli.cleanup._cleanup_pycache", lambda: 5
    )

    result = runner.invoke(cleanup, ["--cache"], obj={"app_context": app_context})
    assert result.exit_code == 0
    assert "Cleaned up 5 __pycache__ director(ies)" in result.output


def test_cleanup_cache_none(runner, app_context, monkeypatch):
    """Test cleanup command correctly reports when no __pycache__ is found."""
    monkeypatch.setattr(
        "bedrock_server_manager.cli.cleanup._cleanup_pycache", lambda: 0
    )

    result = runner.invoke(cleanup, ["--cache"], obj={"app_context": app_context})
    assert result.exit_code == 0
    assert "No __pycache__ directories found to clean" in result.output


def test_cleanup_logs(runner, app_context, tmp_path, monkeypatch):
    """Test cleanup command successfully removes mock .log files."""
    app_context.settings.set("paths.logs", str(tmp_path))
    monkeypatch.setattr(
        "bedrock_server_manager.cli.cleanup._cleanup_log_files", lambda x: 3
    )

    result = runner.invoke(cleanup, ["--logs"], obj={"app_context": app_context})
    assert result.exit_code == 0
    assert "Cleaned up 3 log file(s)" in result.output


def test_cleanup_logs_missing_dir(runner, app_context):
    """Test cleanup command fails gracefully when logs directory is unconfigured."""
    app_context.settings.set("paths.logs", None)
    result = runner.invoke(cleanup, ["--logs"], obj={"app_context": app_context})
    assert result.exit_code == 1  # Abort
    assert "Log directory not specified" in result.output


def test_cleanup_logs_with_override(runner, app_context, tmp_path, monkeypatch):
    """Test cleanup command prioritizes --log-dir override flag."""
    monkeypatch.setattr(
        "bedrock_server_manager.cli.cleanup._cleanup_log_files", lambda x: 1
    )

    result = runner.invoke(
        cleanup,
        ["--logs", "--log-dir", str(tmp_path)],
        obj={"app_context": app_context},
    )
    assert result.exit_code == 0
    assert "Cleaned up 1 log file(s)" in result.output
    assert str(tmp_path) in result.output


def test_internal_cleanup_log_files(tmp_path):
    """Test the internal log file cleanup core logic respecting mtimes."""
    import time

    # Empty dir
    assert _cleanup_log_files(tmp_path) == 0

    # 1 file (kept)
    (tmp_path / "app.log.1").touch()
    assert _cleanup_log_files(tmp_path) == 0
    assert (tmp_path / "app.log.1").exists()

    # 3 files (2 removed, newest kept)
    time.sleep(0.01)
    (tmp_path / "app.log.2").touch()
    time.sleep(0.01)
    (tmp_path / "app.log.3").touch()  # Newest

    assert _cleanup_log_files(tmp_path) == 2
    assert not (tmp_path / "app.log.1").exists()
    assert not (tmp_path / "app.log.2").exists()
    assert (tmp_path / "app.log.3").exists()


def test_internal_cleanup_pycache_error(monkeypatch):
    """Test the internal pycache cleanup logic silently handling exceptions."""

    def mock_rglob(*args, **kwargs):
        raise Exception("Rglob error")

    monkeypatch.setattr(Path, "rglob", mock_rglob)

    assert _cleanup_pycache() == 0
