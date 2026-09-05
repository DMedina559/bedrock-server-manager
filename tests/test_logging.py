"""
Tests for the logging.py module.
"""

import logging
import os
import tempfile
import time
from unittest.mock import patch

from bedrock_server_manager.logging import _prune_old_logs, log_separator, setup_logging


def test_prune_old_logs():
    """Test that old logs are correctly pruned to respect retention limit."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create 7 dummy log files with distinct modified times
        for i in range(1, 8):
            fpath = os.path.join(tmpdir, f"bedrock_server_manager_{i}.log")
            with open(fpath, "w") as f:
                f.write("test")
            os.utime(fpath, (time.time() + i * 10, time.time() + i * 10))

        _prune_old_logs(tmpdir, keep=5)

        remaining = [
            f for f in os.listdir(tmpdir) if f.startswith("bedrock_server_manager_")
        ]
        # Just check that it pruned down to 5
        assert len(remaining) <= 5


def test_setup_logging_creates_handlers():
    """Test setup_logging successfully configures handlers."""
    with tempfile.TemporaryDirectory() as tmpdir:
        import bedrock_server_manager.logging as bsm_logging

        bsm_logging._logging_configured = False

        with patch(
            "bedrock_server_manager.logging.get_config_dir", return_value=tmpdir
        ):
            with patch(
                "bedrock_server_manager.logging.load_config",
                return_value={"logging_level": "DEBUG"},
            ):
                logger = setup_logging(force_reconfigure=True)

                # It should add a console handler and a file handler
                assert len(logger.handlers) >= 2

                # Verify file handler exists and writes to the correct path
                file_handlers = [
                    h for h in logger.handlers if isinstance(h, logging.FileHandler)
                ]
                assert len(file_handlers) >= 1
                assert file_handlers[0].baseFilename.startswith(
                    os.path.join(tmpdir, "logs", "bedrock_server_manager_")
                )

                # Clean up handlers so tempdir can be removed on Windows
                for handler in file_handlers:
                    handler.close()
                    logger.removeHandler(handler)


def test_setup_logging_skips_if_already_configured():
    """Test setup_logging skips if already configured and not forced."""
    import bedrock_server_manager.logging as bsm_logging

    bsm_logging._logging_configured = True

    with patch("logging.getLogger") as mock_get_logger:
        with patch("bedrock_server_manager.logging.load_config", return_value={}):
            with patch(
                "bedrock_server_manager.logging.get_config_dir", return_value="/tmp"
            ):
                setup_logging()

                # Should get the logger and just return it without doing the setup work
                mock_get_logger.return_value.addHandler.assert_not_called()


def test_setup_logging_fallback_on_error():
    """Test setup_logging uses fallback if creating the directory fails."""
    import bedrock_server_manager.logging as bsm_logging

    bsm_logging._logging_configured = False

    # Try to write to a path that isn't allowed (e.g. root without sudo)
    with patch("os.makedirs", side_effect=OSError("Permission denied")):
        with patch("bedrock_server_manager.logging.load_config", return_value={}):
            with patch(
                "bedrock_server_manager.logging.get_config_dir",
                return_value="/root/invalid",
            ):
                logger = logging.getLogger()
                # Ensure root logger has no handlers so the fallback is triggered
                logger.handlers.clear()

                logger = setup_logging(force_reconfigure=True)

                # Should at least have a stream handler as fallback
                assert any(
                    isinstance(h, logging.StreamHandler) for h in logger.handlers
                )


def test_log_separator():
    """Test log_separator writes correctly to active file handlers."""
    logger = logging.getLogger("test_separator")

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "test.log")
        file_handler = logging.FileHandler(log_path)
        logger.addHandler(file_handler)

        log_separator(logger, app_name="TestApp", app_version="1.0")

        file_handler.flush()
        file_handler.close()
        logger.removeHandler(file_handler)

        with open(log_path, "r") as f:
            content = f.read()

        assert "TestApp v1.0" in content
        assert "Operating System" in content
        assert "Timestamp" in content
