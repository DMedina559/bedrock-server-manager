import logging
import os
import warnings

import pytest

from bedrock_server_manager import logging as bsm_logging
from bedrock_server_manager.config import bcm_config
from bedrock_server_manager.logging import _prune_old_logs, log_separator, setup_logging


@pytest.fixture(autouse=True)
def isolated_logging():
    root = logging.getLogger()
    handlers, level, disabled = root.handlers[:], root.level, root.disabled
    configured = bsm_logging._logging_configured
    warnings_handler = logging._warnings_showwarning
    warning_logger = logging.getLogger("py.warnings")
    warning_handlers = warning_logger.handlers[:]
    root.handlers = []
    root.disabled = False
    bsm_logging._logging_configured = False
    with warnings.catch_warnings():
        try:
            yield root
        finally:
            for handler in root.handlers[:]:
                handler.close()
                root.removeHandler(handler)
            root.handlers = handlers
            root.setLevel(level)
            root.disabled = disabled
            bsm_logging._logging_configured = configured
            logging._warnings_showwarning = warnings_handler
            warning_logger.handlers = warning_handlers


def test_prune_old_logs(tmp_path):
    for i in range(7):
        path = tmp_path / f"bedrock_server_manager_{i}.log"
        path.write_text(f"log {i}")
        os.utime(path, (1000000000 + i, 1000000000 + i))
    unrelated = tmp_path / "server.log"
    unrelated.write_text("retain unrelated logs")
    _prune_old_logs(str(tmp_path), keep=5)
    # Pruning reserves a slot for the log created immediately afterward.
    assert {path.name for path in tmp_path.glob("bedrock_server_manager_*.log")} == {
        f"bedrock_server_manager_{i}.log" for i in range(3, 7)
    }
    assert unrelated.read_text() == "retain unrelated logs"


def test_setup_logging_writes_configured_output(isolated_bcm_config, capsys):
    config = bcm_config.load_config()
    config["logging_level"] = "DEBUG"
    bcm_config.save_config(config)
    logger = setup_logging(force_reconfigure=True)
    logger.debug("debug message from real configuration")
    log_separator(logger, app_name="TestApp", app_version="1.0")
    for handler in logger.handlers:
        handler.flush()
    files = list((isolated_bcm_config / "logs").glob("bedrock_server_manager_*.log"))
    assert len(files) == 1
    content = files[0].read_text()
    assert "DEBUG - root - debug message from real configuration" in content
    assert "TestApp v1.0" in content
    assert "Operating System" in content
    assert "Timestamp" in content
    assert "DEBUG: debug message from real configuration" in capsys.readouterr().out
    assert len(logger.handlers) == 2


def test_setup_logging_reuses_existing_handlers(isolated_bcm_config):
    logger = setup_logging()
    original = tuple(logger.handlers)
    assert setup_logging() is logger
    assert tuple(logger.handlers) == original
    assert len(list((isolated_bcm_config / "logs").glob("*.log"))) == 1


def test_setup_logging_falls_back_when_directory_is_a_file(tmp_path, capsys):
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")
    logger = setup_logging(force_reconfigure=True, config_dir=str(blocked))
    logger.warning("fallback remains usable")
    output = capsys.readouterr()
    assert "Could not create log directory" in output.err
    assert "fallback remains usable" in output.out
    assert len(logger.handlers) == 1
    assert not isinstance(logger.handlers[0], logging.FileHandler)
    assert not bsm_logging._logging_configured


def test_log_separator(tmp_path):
    logger = logging.Logger("test_separator")
    path = tmp_path / "separator.log"
    handler = logging.FileHandler(path)
    logger.addHandler(handler)
    try:
        log_separator(logger, app_name="TestApp", app_version="1.0")
        assert "TestApp v1.0" in path.read_text()
        assert "Python Version" in path.read_text()
    finally:
        handler.close()
        logger.removeHandler(handler)
