"""
Tests for the logging.py module.
"""

import logging
import os
import tempfile
from unittest.mock import patch

from bedrock_server_manager.logging import (
    AppAndPluginFilter,
    log_separator,
    setup_logging,
)


def test_app_and_plugin_filter():
    """Test that the filter allows appropriate records."""
    # Ensure cross-platform path matching
    plugin_path = os.path.abspath("/some/plugin/dir")
    filter = AppAndPluginFilter(plugin_dir=plugin_path)

    # Should allow bedrock_server_manager records
    record1 = logging.LogRecord(
        "bedrock_server_manager.test", 10, "/path", 1, "msg", (), None
    )
    assert filter.filter(record1) is True

    # Should allow plugin.* records
    record2 = logging.LogRecord("plugin.my_plugin", 10, "/path", 1, "msg", (), None)
    assert filter.filter(record2) is True

    # Should allow records from plugin dir
    record_path = os.path.join(plugin_path, "test.py")
    record3 = logging.LogRecord("other_module", 10, record_path, 1, "msg", (), None)
    assert filter.filter(record3) is True

    # Should block others
    record4 = logging.LogRecord("uvicorn.error", 10, "/other/path", 1, "msg", (), None)
    assert filter.filter(record4) is False


def test_setup_logging_creates_handlers():
    """Test setup_logging successfully configures handlers."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Import to reset the global state if needed
        import bedrock_server_manager.logging as bsm_logging

        bsm_logging._logging_configured = False

        logger = setup_logging(
            log_dir=tmpdir, log_filename="test.log", force_reconfigure=True
        )

        # It should add a console handler and a file handler
        assert len(logger.handlers) >= 2

        # Verify file handler exists and writes to the correct path
        file_handlers = [
            h
            for h in logger.handlers
            if isinstance(h, logging.handlers.TimedRotatingFileHandler)
        ]
        assert len(file_handlers) >= 1
        assert file_handlers[0].baseFilename == os.path.join(tmpdir, "test.log")

        # Clean up handlers so tempdir can be removed on Windows
        for handler in file_handlers:
            handler.close()
            logger.removeHandler(handler)


def test_setup_logging_skips_if_already_configured():
    """Test setup_logging skips if already configured and not forced."""
    import bedrock_server_manager.logging as bsm_logging

    bsm_logging._logging_configured = True

    with patch("logging.getLogger") as mock_get_logger:
        setup_logging()

        # Should get the logger and just return it without doing the setup work
        mock_get_logger.return_value.addHandler.assert_not_called()


def test_setup_logging_fallback_on_error():
    """Test setup_logging uses fallback if creating the directory fails."""
    import bedrock_server_manager.logging as bsm_logging

    bsm_logging._logging_configured = False

    # Try to write to a path that isn't allowed (e.g. root without sudo)
    with patch("os.makedirs", side_effect=OSError("Permission denied")):
        logger = logging.getLogger()
        # Ensure root logger has no handlers so the fallback is triggered
        logger.handlers.clear()

        logger = setup_logging(log_dir="/root/invalid/path", force_reconfigure=True)

        # Should at least have a stream handler as fallback
        assert any(isinstance(h, logging.StreamHandler) for h in logger.handlers)


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
