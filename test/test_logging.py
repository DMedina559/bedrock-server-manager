import logging
import os
from unittest.mock import MagicMock, patch

import pytest

from bedrock_server_manager.logging import log_separator, setup_logging


@pytest.fixture
def temp_log_dir(tmp_path):
    """Creates a temporary log directory for tests."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return str(log_dir)


class TestLogging:
    def test_setup_logging(self, temp_log_dir):
        """Tests that logging is set up correctly."""
        logger = setup_logging(log_dir=temp_log_dir, force_reconfigure=True)

        handlers = [
            h
            for h in logger.handlers
            if not type(h).__name__ == "_LiveLoggingNullHandler"
        ]
        assert len(handlers) == 2

        file_handler = handlers[0]
        assert isinstance(file_handler, logging.handlers.TimedRotatingFileHandler)
        assert file_handler.level == logging.INFO

        console_handler = handlers[1]
        assert isinstance(console_handler, logging.StreamHandler)
        assert console_handler.level == logging.WARN

    def test_setup_logging_reconfigure(self, temp_log_dir):
        """Tests that logging can be reconfigured."""
        # Initial setup
        setup_logging(log_dir=temp_log_dir, force_reconfigure=True)

        # Reconfigure with different levels
        logger = setup_logging(
            log_dir=temp_log_dir,
            file_log_level=logging.DEBUG,
            cli_log_level=logging.ERROR,
            force_reconfigure=True,
        )

        handlers = [
            h
            for h in logger.handlers
            if not type(h).__name__ == "_LiveLoggingNullHandler"
        ]
        assert len(handlers) == 2
        assert handlers[0].level == logging.DEBUG
        assert handlers[1].level == logging.ERROR

    @patch("os.makedirs", side_effect=OSError)
    def test_setup_logging_dir_creation_error(self, mock_makedirs, capsys):
        """Tests that logging handles directory creation errors."""
        logger = setup_logging(
            log_dir="/non/existent/dir",
            cli_log_level=logging.WARNING,
            force_reconfigure=True,
        )

        captured = capsys.readouterr()
        assert "CRITICAL: Could not create log directory" in captured.err

        handlers = [
            h
            for h in logger.handlers
            if not type(h).__name__ == "_LiveLoggingNullHandler"
        ]
        assert len(handlers) == 0

    def test_log_separator(self, temp_log_dir):
        """Tests that the log separator is written to the file."""
        log_file = os.path.join(temp_log_dir, "bedrock_server_manager.log")
        logger = setup_logging(
            log_dir=temp_log_dir,
            log_filename="bedrock_server_manager.log",
            force_reconfigure=True,
        )

        log_separator(logger, "TestApp", "1.0")

        with open(log_file, "r") as f:
            content = f.read()
            assert "==========" in content
            assert "TestApp v1.0" in content
            assert "Operating System:" in content
