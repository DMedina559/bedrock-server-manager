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
    dependency_levels = {
        name: logging.getLogger(name).level
        for name in ("aiosqlite", "sqlalchemy.engine", "httpcore", "httpx", "httpx2")
    }
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
            for name, dependency_level in dependency_levels.items():
                logging.getLogger(name).setLevel(dependency_level)
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
    assert len([h for h in logger.handlers if getattr(h, "_bsm_handler", False)]) == 2


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
    assert "File logging unavailable" in output.out
    assert "fallback remains usable" in output.out
    assert len([h for h in logger.handlers if getattr(h, "_bsm_handler", False)]) == 1
    assert not any(isinstance(h, logging.FileHandler) for h in logger.handlers)
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


def test_repeated_setup_updates_handler_levels(isolated_bcm_config, capsys):
    logger = setup_logging(log_level="WARNING")
    original = tuple(logger.handlers)
    setup_logging(log_level="debug")
    logger.debug("new level is active")
    assert tuple(logger.handlers) == original
    assert all(
        handler.level == logging.DEBUG
        for handler in original
        if getattr(handler, "_bsm_handler", False)
    )
    assert "new level is active" in capsys.readouterr().out


def test_reconfigure_preserves_host_handler_and_creates_distinct_files(
    isolated_bcm_config,
):
    import io

    root = logging.getLogger()
    output = io.StringIO()
    host_handler = logging.StreamHandler(output)
    root.addHandler(host_handler)
    setup_logging(log_level="INFO")
    old_file = next(h for h in root.handlers if isinstance(h, logging.FileHandler))
    setup_logging(force_reconfigure=True, log_level="INFO")
    root.info("host still receives records")
    assert host_handler in root.handlers
    assert "host still receives records" in output.getvalue()
    assert old_file.stream is None
    assert len(list((isolated_bcm_config / "logs").glob("*.log"))) == 2
    assert len([h for h in root.handlers if getattr(h, "_bsm_handler", False)]) == 2


def test_invalid_level_falls_back_to_info(isolated_bcm_config, capsys):
    logger = setup_logging(log_level="not-a-level")
    assert logger.level == logging.INFO
    assert "Invalid logging level" in capsys.readouterr().out


@pytest.mark.parametrize("level,console_traceback", [("INFO", False), ("DEBUG", True)])
def test_error_output_keeps_diagnostics_in_file(
    isolated_bcm_config, capsys, level, console_traceback
):
    logger = setup_logging(log_level=level)
    try:
        raise RuntimeError("request failed: password='two secret words'")
    except RuntimeError:
        logger.exception("Could not finish operation\nINFO: forged line\x1b[31m")
    output = capsys.readouterr().out
    for handler in logger.handlers:
        handler.flush()
    file = next((isolated_bcm_config / "logs").glob("*.log"))
    content = file.read_text()
    assert ("Traceback (most recent call last)" in output) is console_traceback
    assert "Traceback (most recent call last)" in content
    assert "two secret words" not in output + content
    assert "\\x0aINFO: forged line\\x1b[31m" in output
    assert "\\x0aINFO: forged line\\x1b[31m" in content


@pytest.mark.parametrize(
    "message,secret",
    [
        ("URL https://user:my-password@example.com/path", "my-password"),
        ("GET /register?token=private-token&role=admin", "private-token"),
        ('{"password": "two secret words"}', "two secret words"),
        ("Authorization: Bearer private-bearer", "private-bearer"),
        ("access_token='private-token'", "private-token"),
        ("GET /app/register/private-link-token", "private-link-token"),
    ],
)
def test_formatter_redacts_credentials_without_changing_record(message, secret):
    record = logging.LogRecord(
        "example", logging.WARNING, __file__, 1, "%s", (message,), None
    )
    formatter = bsm_logging.ApplicationFormatter("%(message)s")
    assert secret not in formatter.format(record)
    assert "[redacted]" in formatter.format(record)
    assert record.getMessage() == message


def test_retry_failure_reporting_and_recovery(caplog, monkeypatch):
    logger = logging.getLogger("retry-test")
    reporter = bsm_logging.RepeatedFailureReporter(logger)
    now = [0.0]
    monkeypatch.setattr(bsm_logging.time, "monotonic", lambda: now[0])
    with caplog.at_level(logging.INFO):
        for _ in range(5):
            reporter.report(
                "app log", "Could not read %s: %s; retrying.", OSError("access denied")
            )
        assert len(caplog.records) == 1
        now[0] = 60.0
        reporter.report(
            "app log", "Could not read %s: %s; retrying.", OSError("access denied")
        )
        reporter.recover("app log")
        reporter.recover("app log")
        assert len(caplog.records) == 3
        assert caplog.records[-1].levelno == logging.INFO
        assert "recovered" in caplog.records[-1].message


async def test_server_polling_is_quiet_and_lifecycle_remains_visible(
    real_bedrock_server, caplog
):
    server = real_bedrock_server
    caplog.clear()
    with caplog.at_level(logging.INFO):
        await server.start()
        await server.send_command("say private-command-content")
        await server.stop()
    records = [
        record
        for record in caplog.records
        if record.name.startswith("bedrock_server_manager")
    ]
    messages = [record.getMessage() for record in records]
    assert any("started (PID" in message for message in messages)
    assert any("stopped." in message for message in messages)
    assert "private-command-content" not in "\n".join(messages)
    assert not any(record.levelno >= logging.WARNING for record in records)
    caplog.clear()
    with caplog.at_level(logging.INFO):
        for _ in range(3):
            assert not await server.is_running()
            await server.get_status()
            await server.get_summary_info()
    assert not [
        record
        for record in caplog.records
        if record.name.startswith("bedrock_server_manager")
    ]


async def test_setting_write_does_not_log_value(app_context, caplog):
    from bedrock_server_manager.api.models.settings import SetGlobalSettingRequest
    from bedrock_server_manager.api.settings import set_global_setting

    setup_logging(config_dir=app_context.settings.config_dir, log_level="DEBUG")
    secret = "sensitive-setting-test-value"
    with caplog.at_level(logging.DEBUG):
        await set_global_setting(
            SetGlobalSettingRequest(key="custom.logging_test", value=secret),
            app_context=app_context,
        )
    assert secret not in caplog.text
    assert "custom.logging_test" in caplog.text


async def test_registration_logs_actor_without_link(admin_auth_client, caplog):
    with caplog.at_level(logging.INFO):
        response = await admin_auth_client.post(
            "/api/register/generate-token", json={"role": "user"}
        )
    assert response.status_code == 200
    link = response.json()["registration_url"]
    assert link not in caplog.text
    assert link.rsplit("/", 1)[-1] not in caplog.text
    assert "Registration link created" in caplog.text


async def test_web_log_view_uses_active_session_over_legacy_file(app_context):
    from pathlib import Path

    logger = setup_logging(config_dir=app_context.settings.config_dir, log_level="INFO")
    legacy = Path(app_context.log_dir) / "bedrock_server_manager.log"
    legacy.write_text("old session\n")
    logger.info("current session")
    for handler in logger.handlers:
        handler.flush()
    path = await app_context.log_streamer._get_app_log_path()
    assert path != str(legacy)
    assert "current session" in Path(path).read_text()


def test_propagated_and_wrapped_failure_is_reported_once(caplog):
    logger = logging.getLogger("operation-test")
    with caplog.at_level(logging.DEBUG):
        try:
            raise RuntimeError("filesystem unavailable")
        except RuntimeError as original:
            bsm_logging.log_operation_error(
                logger, "Backup failed: %s", original, error=original
            )
            wrapped = RuntimeError("API operation failed")
            wrapped.__cause__ = original
            bsm_logging.log_operation_error(
                logger, "HTTP operation failed", error=wrapped
            )
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.ERROR
    assert caplog.records[0].exc_info is not None


def test_expected_operation_rejection_is_debug_only(caplog):
    from bedrock_server_manager.error import UserInputError

    error = UserInputError("Invalid backup selection")
    with caplog.at_level(logging.DEBUG):
        bsm_logging.log_operation_error(
            logging.getLogger("operation-test"),
            "Request rejected: %s",
            error,
            error=error,
        )
    assert caplog.records[-1].levelno == logging.DEBUG
    assert caplog.records[-1].exc_info is None


def test_fallback_failure_is_reported_separately(caplog):
    logger = logging.getLogger("operation-test")
    with caplog.at_level(logging.ERROR):
        try:
            raise RuntimeError("first failure")
        except RuntimeError as first:
            bsm_logging.log_operation_error(
                logger, "First operation failed", error=first
            )
            try:
                raise RuntimeError("fallback failure")
            except RuntimeError as fallback:
                bsm_logging.log_operation_error(
                    logger, "Fallback failed", error=fallback
                )
    assert len(caplog.records) == 2


@pytest.mark.parametrize("verbosity", [logging.INFO, logging.DEBUG])
def test_expected_failure_does_not_hide_operational_failure(caplog, verbosity):
    from bedrock_server_manager.error import UserInputError

    logger = logging.getLogger("operation-escalation")
    expected = UserInputError("selection invalid")
    failure = RuntimeError("automatic backup failed")
    failure.__cause__ = expected
    with caplog.at_level(verbosity):
        bsm_logging.log_operation_error(logger, "Selection rejected", error=expected)
        bsm_logging.log_operation_error(
            logger, "Automatic backup failed", error=failure
        )
    errors = [record for record in caplog.records if record.levelno == logging.ERROR]
    assert len(errors) == 1
    assert errors[0].exc_info[1] is failure


def test_missing_essential_file_is_an_operational_error(caplog):
    from bedrock_server_manager.error import AppFileNotFoundError

    with caplog.at_level(logging.INFO):
        bsm_logging.log_operation_error(
            logging.getLogger("operation-test"),
            "Backup file unavailable",
            error=AppFileNotFoundError("world missing"),
        )
    assert caplog.records[-1].levelno == logging.ERROR


def test_escaped_quoted_credentials_and_logger_controls_are_safe():
    record = logging.LogRecord(
        "plugin\nINFO: forged\u2028",
        logging.INFO,
        __file__,
        1,
        '{"password":"first\\"second secret", "jwt_secret_key":"jwt-secret"}',
        (),
        None,
    )
    output = bsm_logging.ApplicationFormatter("%(name)s: %(message)s").format(record)
    assert "second secret" not in output
    assert "jwt-secret" not in output
    assert "\n" not in output
    assert "\u2028" not in output
    assert "\\x0a" in output


def test_rotating_session_logs_and_retention(isolated_bcm_config, monkeypatch):
    monkeypatch.setattr(bsm_logging, "MAX_LOG_BYTES", 256)
    logger = setup_logging(log_level="INFO")
    for i in range(20):
        logger.info("Operation %s completed with diagnostic context %s", i, "x" * 50)
    log_dir = isolated_bcm_config / "logs"
    active = bsm_logging.get_application_log_path(str(log_dir))
    assert active is not None
    assert len(list(log_dir.glob("*.log.*"))) == 4
    from pathlib import Path

    assert "Operation 19 completed" in Path(active).read_text(encoding="utf-8")
    for handler in logger.handlers:
        handler.close()
    _prune_old_logs(str(log_dir), keep=1)
    assert not list(log_dir.glob("*.log*"))
