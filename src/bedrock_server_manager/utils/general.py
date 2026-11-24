# bedrock_server_manager/utils/general.py
"""Provide general utility functions for the application.

Includes startup checks, timestamp generation, and interactive prompts.
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, List

from ..error import AppFileNotFoundError, FileOperationError
from ..logging import log_operation_error

logger = logging.getLogger(__name__)


def startup_checks(
    settings: Any,
) -> None:
    """Performs initial checks and setup when the application starts.

    - Verifies Python version compatibility (>= 3.11).
    - Creates essential application directories based on settings.

    :param settings: Settings instance or object providing paths configuration."""
    # Python Version Check
    if sys.version_info < (3, 11):
        message = "Python version 3.11 or later is required. You are running {}.{}.{}.".format(
            sys.version_info.major, sys.version_info.minor, sys.version_info.micro
        )
        logger.critical(message)
        raise RuntimeError(message)

    # Accept either Settings object directly or derive from AppContext if passed
    if hasattr(settings, "settings"):
        settings = settings.settings

    # Ensure essential directories exist
    config_dir = getattr(settings, "config_dir", None)
    dirs_to_create = {
        "SERVERS_DIR": settings.get("paths.servers"),
        "CONTENT_DIR": settings.get("paths.content"),
        "WORLDS_SUBDIR": (
            os.path.join(str(settings.get("paths.content")), "worlds")
            if settings.get("paths.content")
            else None
        ),
        "ADDONS_SUBDIR": (
            os.path.join(str(settings.get("paths.content")), "addons")
            if settings.get("paths.content")
            else None
        ),
        "DOWNLOAD_DIR": settings.get("paths.downloads"),
        "PLUGIN_DIR": settings.get("paths.plugins"),
        "BACKUP_DIR": settings.get("paths.backups"),
        "RUNTIME_DIR": (
            os.path.join(str(config_dir), "runtime") if config_dir else None
        ),
        "SERVER_LOGS_DIR": (
            os.path.join(str(config_dir), "logs", "servers") if config_dir else None
        ),
        "PLUGIN_DATA_PUBLIC_DIR": (
            os.path.join(str(config_dir), "plugins", "public") if config_dir else None
        ),
    }

    logger.debug("Insuring essential directories exist...")

    for name, dir_path in dirs_to_create.items():
        if dir_path and isinstance(dir_path, str):
            try:
                os.makedirs(dir_path, exist_ok=True)
            except OSError as e:
                log_operation_error(
                    logger, "Failed to create directory %s: %s", dir_path, e, error=e
                )
        elif not dir_path:
            logger.warning(
                "Directory path for '%s' is missing in settings. Skipping creation.",
                name,
            )

    if config_dir and isinstance(config_dir, str):
        _migrate_legacy_layout(
            config_dir=config_dir,
            servers_dir=settings.get("paths.servers"),
            backups_dir=settings.get("paths.backups"),
        )

    logger.debug("Startup checks completed.")


_RESERVED_CONFIG_SUBDIRS = frozenset(
    {
        "bootstrap",
        "config",
        "credentials",
        "data",
        "db",
        "logs",
        "plugins",
        "runtime",
    }
)


def _migrate_legacy_layout(
    config_dir: str,
    servers_dir: Any = None,
    backups_dir: Any = None,
) -> None:
    """Migrate legacy root/server runtime, log, and plugin files into their scoped directories."""
    runtime_dir = os.path.join(config_dir, "runtime")
    os.makedirs(runtime_dir, exist_ok=True)

    # 1. Legacy web runtime files in <config_dir>
    for filename in ("web_server.pid", "web_server.lock", "web_server.control.json"):
        legacy_file = os.path.join(config_dir, filename)
        target_file = os.path.join(runtime_dir, filename)
        if os.path.isfile(legacy_file):
            try:
                if not os.path.exists(target_file):
                    os.replace(legacy_file, target_file)
                else:
                    os.unlink(legacy_file)
            except OSError:
                pass

    # 2. Legacy plugin doc files in <config_dir> and <backups_dir>
    plugin_docs_dir = os.path.join(config_dir, "plugins", "api_docs_generator")
    for doc_name in ("PLUGIN_API_REFERENCE.md", "PLUGIN_EVENT_REFERENCE.md"):
        for source_dir in (config_dir, backups_dir):
            if not source_dir or not isinstance(source_dir, str):
                continue
            legacy_doc = os.path.join(source_dir, doc_name)
            if os.path.isfile(legacy_doc):
                try:
                    os.makedirs(plugin_docs_dir, exist_ok=True)
                    target_doc = os.path.join(plugin_docs_dir, doc_name)
                    if not os.path.exists(target_doc):
                        os.replace(legacy_doc, target_doc)
                    else:
                        os.unlink(legacy_doc)
                except OSError:
                    pass

    # 3. Per-server legacy runtime dirs (<config_dir>/<server_name>) and logs (<servers_dir>/<server_name>/server_output.txt)
    if servers_dir and isinstance(servers_dir, str) and os.path.isdir(servers_dir):
        try:
            server_names = [
                entry
                for entry in os.listdir(servers_dir)
                if os.path.isdir(os.path.join(servers_dir, entry))
            ]
        except OSError:
            server_names = []

        for server_name in server_names:
            target_runtime_dir = os.path.join(runtime_dir, "servers", server_name)
            os.makedirs(target_runtime_dir, exist_ok=True)

            if server_name not in _RESERVED_CONFIG_SUBDIRS:
                legacy_server_cfg_dir = os.path.join(config_dir, server_name)
                if os.path.isdir(legacy_server_cfg_dir):
                    try:
                        for item in os.listdir(legacy_server_cfg_dir):
                            src_item = os.path.join(legacy_server_cfg_dir, item)
                            dst_item = os.path.join(target_runtime_dir, item)
                            if os.path.isfile(src_item):
                                if not os.path.exists(dst_item):
                                    os.replace(src_item, dst_item)
                                else:
                                    os.unlink(src_item)
                        os.rmdir(legacy_server_cfg_dir)
                    except OSError:
                        pass

            target_log_dir = os.path.join(config_dir, "logs", "servers", server_name)
            os.makedirs(target_log_dir, exist_ok=True)
            for legacy_log_path in (
                os.path.join(servers_dir, server_name, "server_output.txt"),
                os.path.join(target_log_dir, "server_output.txt"),
                os.path.join(target_log_dir, "server_output.log"),
            ):
                if os.path.isfile(legacy_log_path):
                    try:
                        if os.path.getsize(legacy_log_path) > 0:
                            from uuid import uuid4

                            mtime = datetime.fromtimestamp(
                                os.path.getmtime(legacy_log_path), timezone.utc
                            ).strftime("%Y%m%d_%H%M%S_%f")
                            target_log_path = os.path.join(
                                target_log_dir,
                                f"{server_name}_{mtime}_{os.getpid()}_{uuid4().hex}.log",
                            )
                            try:
                                os.replace(legacy_log_path, target_log_path)
                            except PermissionError:
                                import shutil

                                shutil.copy2(legacy_log_path, target_log_path)
                        else:
                            os.unlink(legacy_log_path)
                    except OSError:
                        pass


def run_async(coro):
    """Run a coroutine from synchronous CLI code.

    The legacy active-loop path blocks its caller and uses another event loop.
    Async consumers must await their coroutine directly; loop-bound application
    resources must remain on their owning loop.
    """
    import asyncio
    import concurrent.futures

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(lambda: asyncio.run(coro)).result()


class ReentrantAsyncLock:
    """A re-entrant lock for asyncio tasks to prevent deadlocks when a task re-enters locked operations."""

    def __init__(self) -> None:
        self._lock: asyncio.Lock | None = None
        self._owner: Any = None
        self._count = 0
        self._waiting = 0
        self._created_loop: asyncio.AbstractEventLoop | None = None

    def _get_lock(self) -> asyncio.Lock:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if self._lock is None:
            self._lock = asyncio.Lock()
            self._created_loop = loop
        elif loop is not None:
            owner_loop = None
            if self._owner is not None and hasattr(self._owner, "get_loop"):
                try:
                    owner_loop = self._owner.get_loop()
                except Exception:
                    pass

            lock_loop = getattr(self._lock, "_loop", None)

            if (
                self._created_loop is not loop
                or (self._created_loop is not None and self._created_loop.is_closed())
                or (
                    lock_loop is not None
                    and (lock_loop is not loop or lock_loop.is_closed())
                )
                or (
                    owner_loop is not None
                    and (owner_loop is not loop or owner_loop.is_closed())
                )
            ):
                self._lock = asyncio.Lock()
                self._created_loop = loop
                self._owner = None
                self._count = 0

        return self._lock

    async def acquire(self, timeout: float | None = None) -> bool:
        lock = self._get_lock()
        me = asyncio.current_task()
        if me is not None and self._owner == me:
            self._count += 1
            return True

        started = time.monotonic()
        contended = lock.locked()
        if contended:
            from .progress import report_stage

            logger.debug("Waiting for operation lock (timeout_seconds=%s)", timeout)
            await report_stage("Waiting for another operation")
        self._waiting += 1
        try:
            if timeout is not None:
                await asyncio.wait_for(lock.acquire(), timeout=timeout)
            else:
                await lock.acquire()
        except TimeoutError:
            logger.warning(
                "Operation lock timed out after %.3f seconds",
                time.monotonic() - started,
            )
            raise
        finally:
            self._waiting -= 1

        if contended:
            logger.debug(
                "Operation lock acquired after %.3f seconds", time.monotonic() - started
            )
        self._owner = me
        self._count = 1
        return True

    def release(self) -> None:
        lock = self._get_lock()
        me = asyncio.current_task()
        if me is None or self._owner != me:
            raise RuntimeError(
                "Cannot release un-acquired lock or lock owned by another task"
            )
        self._count -= 1
        if self._count == 0:
            self._owner = None
            lock.release()

    @property
    def waiting(self) -> int:
        return self._waiting

    def locked(self) -> bool:
        lock = self._get_lock()
        return bool(lock.locked())

    async def __aenter__(self) -> "ReentrantAsyncLock":
        await self.acquire()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()


def get_timestamp() -> str:
    """Generates a timestamp string suitable for filenames or logging.

    :returns: The current UTC timestamp in YYYYMMDD_HHMMSS format.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return timestamp


async def list_content_files(
    content_dir: str | None, sub_folder: str, extensions: List[str]
) -> List[str]:
    """
    Internal helper to list files with specified extensions from a sub-folder
    within the global content directory.
    """
    import aiofiles.ospath

    from ..core.system import find_files

    if not content_dir or not await aiofiles.ospath.isdir(content_dir):
        raise AppFileNotFoundError(str(content_dir), "Content directory")

    target_dir = os.path.join(content_dir, sub_folder)
    if not await aiofiles.ospath.isdir(target_dir):
        logger.debug(
            "Content sub-directory '%s' not found. Returning empty list.", target_dir
        )
        return []

    found_files: List[str] = []
    try:
        for ext in extensions:
            pattern = f"*{ext}" if ext.startswith(".") else f"*.{ext}"
            files = await find_files(target_dir, pattern=pattern)
            found_files.extend(os.path.abspath(str(f)) for f in files)
    except OSError as e:
        raise FileOperationError(
            f"Error scanning content directory {target_dir}: {e}"
        ) from e
    return sorted(list(set(found_files)))
