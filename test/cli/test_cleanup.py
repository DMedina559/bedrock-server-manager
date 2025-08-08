import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from bedrock_server_manager.cli import cleanup


@patch("bedrock_server_manager.cli.cleanup._cleanup_pycache")
def test_cleanup_no_options(mocker):
    runner = CliRunner()
    mock_app_context = mocker.MagicMock()
    result = runner.invoke(
        cleanup.cleanup,
        obj={"app_context": mock_app_context, "bsm": MagicMock(), "cli": MagicMock()},
    )
    assert result.exit_code == 0
    assert "No cleanup options specified" in result.output


@patch("bedrock_server_manager.cli.cleanup._cleanup_pycache", return_value=1)
def test_cleanup_cache(mock_cleanup_pycache, mocker):
    runner = CliRunner()
    mock_app_context = mocker.MagicMock()
    result = runner.invoke(
        cleanup.cleanup,
        ["--cache"],
        obj={"app_context": mock_app_context, "bsm": MagicMock(), "cli": MagicMock()},
    )
    assert result.exit_code == 0
    mock_cleanup_pycache.assert_called_once()


def test_cleanup_logs(mocker):
    runner = CliRunner()
    with runner.isolated_filesystem():
        log_dir = Path("logs")
        log_dir.mkdir()
        (log_dir / "log1.log.1").touch()
        time.sleep(0.1)
        (log_dir / "log2.log.2").touch()

        mock_app_context = mocker.MagicMock()
        mock_app_context.settings.get.return_value = str(log_dir)

        result = runner.invoke(
            cleanup.cleanup,
            ["--logs"],
            obj={
                "app_context": mock_app_context,
                "bsm": MagicMock(),
                "cli": MagicMock(),
            },
        )

        assert result.exit_code == 0
        assert (log_dir / "log2.log.2").exists()
        assert not (log_dir / "log1.log.1").exists()


@patch("bedrock_server_manager.cli.cleanup._cleanup_pycache", return_value=1)
def test_cleanup_all(mock_cleanup_pycache, mocker):
    runner = CliRunner()
    with runner.isolated_filesystem():
        log_dir = Path("logs")
        log_dir.mkdir()
        (log_dir / "log1.log.1").touch()
        time.sleep(0.1)
        (log_dir / "log2.log.2").touch()

        mock_app_context = mocker.MagicMock()
        mock_app_context.settings.get.return_value = str(log_dir)

        result = runner.invoke(
            cleanup.cleanup,
            ["--cache", "--logs"],
            obj={
                "app_context": mock_app_context,
                "bsm": MagicMock(),
                "cli": MagicMock(),
            },
        )

        assert result.exit_code == 0
        mock_cleanup_pycache.assert_called_once()
        assert not (log_dir / "log1.log.1").exists()
        assert (log_dir / "log2.log.2").exists()


def test_cleanup_log_dir_override(mocker):
    runner = CliRunner()
    with runner.isolated_filesystem():
        log_dir = Path("custom_logs")
        log_dir.mkdir()
        (log_dir / "log1.log.1").touch()
        time.sleep(0.1)
        (log_dir / "log2.log.2").touch()

        mock_app_context = mocker.MagicMock()

        result = runner.invoke(
            cleanup.cleanup,
            ["--logs", "--log-dir", str(log_dir)],
            obj={
                "app_context": mock_app_context,
                "bsm": MagicMock(),
                "cli": MagicMock(),
            },
        )

        assert result.exit_code == 0
        assert (log_dir / "log2.log.2").exists()
        assert not (log_dir / "log1.log.1").exists()
