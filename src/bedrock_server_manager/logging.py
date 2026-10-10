"""Application logging with concise console output and diagnostic file records."""

import copy
import glob
import logging
import os
import platform
import re
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional

from .error import (
    APICancelledError,
    ServerNotRunningError,
    UserInputError,
)

DEFAULT_LOG_KEEP = 5
MAX_LOG_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 4
_logging_configured = False
_HANDLER_MARKER = "_bsm_handler"

# Protect common credential representations in URLs, messages, and tracebacks.
_CREDENTIAL = re.compile(
    r"(?i)(\b(?:access_token|refresh_token|token|password|secret|jwt_secret_key|authorization|api_key)"
    r"['\"]?\s*[:=]\s*)(?:\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|[^\s&,'\"}]+)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[^\s,;\'\"]+")
_URL_CREDENTIAL = re.compile(r"(https?://)[^/\s:@]+:[^/\s@]+@", re.IGNORECASE)
_REGISTRATION_LINK = re.compile(
    r"((?:/app/register|/api/register/validate)/)[^/\s?'\"#]+"
)


def log_operation_error(
    logger: logging.Logger | logging.LoggerAdapter,
    message: str,
    *args: object,
    error: Exception,
) -> None:
    """Report a failure once as it propagates through application layers.

    Expected input and state conflicts are DEBUG diagnostics.
    Operational failures retain their traceback. Wrapping a reported exception
    preserves its reporting ownership through the exception cause chain.
    """
    expected = isinstance(
        error, (UserInputError, ServerNotRunningError, APICancelledError)
    )
    level = logging.DEBUG if expected else logging.ERROR
    if not logger.isEnabledFor(level):
        return
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if getattr(current, "_bsm_failure_log_level", 0) >= level:
            return
        current = current.__cause__
    logger.log(
        level,
        message,
        *args,
        exc_info=(type(error), error, error.__traceback__) if not expected else None,
    )
    setattr(error, "_bsm_failure_log_level", level)


class RepeatedFailureReporter:
    """Report a retrying background failure once per minute, and its recovery."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.failures: dict[str, tuple[type[Exception], str, float]] = {}

    def report(self, key: str, message: str, error: Exception) -> None:
        now = time.monotonic()
        previous = self.failures.get(key)
        signature = (type(error), str(error))
        if previous is None or previous[:2] != signature or now - previous[2] >= 60:
            self.logger.warning(message, key, error, exc_info=True)
            self.failures[key] = (*signature, now)

    def recover(self, key: str) -> None:
        if self.failures.pop(key, None) is not None:
            self.logger.info("Background service recovered: %s.", key)


class _TransportFilter(logging.Filter):
    """Keep HTTP access and routine WebSocket lifecycle records at DEBUG."""

    def filter(self, record: logging.LogRecord) -> bool:
        routine = record.name == "uvicorn.access" or (
            record.msg in ("connection open", "connection closed")
            or ('"WebSocket %s" [accepted]' in str(record.msg))
        )
        if routine and record.levelno == logging.INFO:
            record.levelno = logging.DEBUG
            record.levelname = "DEBUG"
        return True


def configure_web_logging() -> None:
    """Inherit application verbosity without replacing host handlers."""
    for name in ("uvicorn.error", "uvicorn.access", "uvicorn.asgi"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.NOTSET)
        logger.propagate = True
        if not any(isinstance(f, _TransportFilter) for f in logger.filters):
            logger.addFilter(_TransportFilter())


def _safe_text(value: str) -> str:
    value = _URL_CREDENTIAL.sub(r"\1[redacted]@", value)
    value = _REGISTRATION_LINK.sub(r"\1[redacted]", value)
    value = _BEARER.sub("Bearer [redacted]", value)
    return _CREDENTIAL.sub(r"\1[redacted]", value)


class ApplicationFormatter(logging.Formatter):
    """Keep records safe for plain-text viewers without mutating shared records.

    Console tracebacks are shown only when DEBUG logging is enabled. Files retain
    tracebacks at every level. Embedded control characters cannot create fake log
    lines or terminal escape sequences; formatter-generated tracebacks stay multiline.
    """

    def __init__(self, fmt: str, *, console: bool = False):
        super().__init__(fmt)
        self.console = console

    @staticmethod
    def _escape_controls(value: str) -> str:
        return "".join(
            (
                f"\\x{ord(char):02x}"
                if ord(char) < 32 or 127 <= ord(char) <= 159 or char in "\u2028\u2029"
                else char
            )
            for char in value
        )

    def formatException(self, ei) -> str:
        text = super().formatException(ei)
        return "".join(
            "\n" if char == "\n" else self._escape_controls(char) for char in text
        )

    def format(self, record: logging.LogRecord) -> str:
        local = copy.copy(record)
        message = _safe_text(record.getMessage())
        server_name = getattr(record, "server_name", None)
        if server_name is not None:
            local.name = "%s [server=%s]" % (record.name, _safe_text(str(server_name)))
            if self.console and str(server_name) not in message:
                message = "Server '%s': %s" % (server_name, message)
        local.name = self._escape_controls(_safe_text(local.name))
        local.msg = self._escape_controls(message)
        local.args = ()
        # Another handler's formatter may have populated this cache already.
        local.exc_text = None
        if self.console and not logging.getLogger().isEnabledFor(logging.DEBUG):
            local.exc_info = None
            local.stack_info = None
        return _safe_text(super().format(local))


def _prune_old_logs(
    log_dir: str, base_name: str = "bedrock_server_manager", keep: int = 5
) -> None:
    """Reserve one retention slot for the log about to be created."""
    if keep < 1:
        raise ValueError("Log retention must be at least one file.")
    try:
        files = glob.glob(os.path.join(log_dir, f"{glob.escape(base_name)}_*.log"))
        files.sort(key=os.path.getmtime)
        for path in files[: max(0, len(files) - keep + 1)]:
            try:
                os.remove(path)
                for rotated in glob.glob(f"{glob.escape(path)}.*"):
                    if rotated.rsplit(".", 1)[-1].isdigit():
                        os.remove(rotated)
            except OSError as error:
                logging.getLogger(__name__).warning(
                    "Could not remove old log '%s': %s", path, error
                )
    except OSError as error:
        logging.getLogger(__name__).warning(
            "Could not prune logs in '%s': %s", log_dir, error
        )


def _configure_handler(handler: logging.Handler, level: int, *, console: bool) -> None:
    setattr(handler, _HANDLER_MARKER, True)
    handler.setLevel(level)
    handler.setFormatter(
        ApplicationFormatter(
            (
                "%(levelname)s: %(message)s"
                if console
                else "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
            ),
            console=console,
        )
    )


def get_application_log_path(log_dir: str) -> str | None:
    """Return the file this process writes in the requested log directory."""
    directory = os.path.normcase(os.path.realpath(log_dir))
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.FileHandler) and getattr(
            handler, _HANDLER_MARKER, False
        ):
            if (
                os.path.normcase(
                    os.path.realpath(os.path.dirname(handler.baseFilename))
                )
                == directory
            ):
                return handler.baseFilename
    return None


def setup_logging(
    force_reconfigure: bool = False,
    config_dir: Optional[str] = None,
    log_level: Optional[str] = None,
) -> logging.Logger:
    """Configure BSM handlers while preserving handlers installed by the host.

    Reconfiguration replaces only owned handlers. Repeated setup updates all
    owned handler levels, and a failed file setup leaves console logging usable.
    """
    global _logging_configured
    from .config.bcm_config import get_config_dir, load_config

    requested_level = (
        log_level
        if log_level is not None
        else load_config().get("logging_level", "INFO")
    )
    level = logging.getLevelName(str(requested_level).upper())
    invalid_level = not isinstance(level, int)
    if invalid_level:
        level = logging.INFO
    root = logging.getLogger()
    root.setLevel(level)
    # Dependency DEBUG records can dump SQL bind values and request URLs. Keep
    # their warnings/errors while application diagnostics remain independently usable.
    for name in ("aiosqlite", "sqlalchemy.engine", "httpcore", "httpx", "httpx2"):
        logging.getLogger(name).setLevel(logging.WARNING)
    owned = [
        handler for handler in root.handlers if getattr(handler, _HANDLER_MARKER, False)
    ]
    if _logging_configured and owned and not force_reconfigure:
        for handler in owned:
            handler.setLevel(level)
        if invalid_level:
            root.warning("Invalid logging level %r; using INFO.", requested_level)
        return root
    for handler in owned:
        root.removeHandler(handler)
        handler.close()
    _logging_configured = False

    console = logging.StreamHandler(sys.stdout)
    _configure_handler(console, level, console=True)
    root.addHandler(console)
    if invalid_level:
        root.warning("Invalid logging level %r; using INFO.", requested_level)

    log_dir = os.path.join(
        config_dir if config_dir is not None else get_config_dir(), "logs"
    )
    try:
        os.makedirs(log_dir, exist_ok=True)
        _prune_old_logs(log_dir, keep=DEFAULT_LOG_KEEP)
        # Separate simultaneous sessions and immediate reconfiguration on Windows.
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = os.path.join(
            log_dir, f"bedrock_server_manager_{timestamp}_{os.getpid()}.log"
        )
        file_handler = RotatingFileHandler(
            path, maxBytes=MAX_LOG_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
        )
        _configure_handler(file_handler, level, console=False)
        root.addHandler(file_handler)
        _logging_configured = True
    except OSError as error:
        root.warning(
            "File logging unavailable in '%s': %s; console logging remains enabled.",
            log_dir,
            error,
        )

    logging.captureWarnings(True)
    root.debug("Logging configured at %s.", logging.getLevelName(level))
    return root


def log_separator(
    logger: logging.Logger,
    app_name: Optional[str] = None,
    app_version: str = "0.0.0",
) -> None:
    """Write session metadata to owned file handlers under their output locks."""
    os_info = f'{platform.system()} {platform.version() if platform.system() == "Windows" else platform.release()}'
    lines = [
        "=" * 100,
        f'{app_name or "Application"} v{app_version}',
        f"Operating System: {os_info}",
        f"Python Version: {platform.python_version()}",
        f"Timestamp: {datetime.now():%Y-%m-%d %H:%M:%S}",
        "=" * 100,
    ]
    for handler in logger.handlers:
        if not isinstance(handler, logging.FileHandler):
            continue
        handler.acquire()
        try:
            if handler.stream is not None and not handler.stream.closed:
                handler.stream.write(
                    "\n" + "\n".join(_safe_text(line) for line in lines) + "\n\n"
                )
                handler.flush()
        except OSError:
            logger.exception("Could not write log session metadata.")
        finally:
            handler.release()
