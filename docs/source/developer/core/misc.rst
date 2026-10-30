.. Bedrock Server Manager Miscellaneous Core documentation file

Miscellaneous Core Documentation
================================

.. autofunction:: bedrock_server_manager.core.downloader.prune_old_downloads

Logging
-------

Use a module logger and deferred formatting, for example
``logger.info("Server '%s' started (PID %s).", name, pid)``. Keep messages
short, identify the affected server or resource, and describe the outcome.

* DEBUG: polling, subscriptions, internal setup, intermediate steps, and no-op actions.
* INFO: meaningful actions, completed operations, and recovery.
* WARNING: recoverable problems, rejected security-sensitive actions, or degraded operation.
* ERROR: an operation failed or automatic recovery was exhausted.
* CRITICAL: the application cannot start or continue.

Avoid logging passwords, tokens, registration links, raw commands, setting values,
or complete request/response payloads. ``log_operation_error`` classifies expected
rejections and retains reporting ownership when the same exception is re-raised or
wrapped.

Each session keeps its active log file plus up to four 10 MiB rotated files;
startup retains five sessions. The web log viewer streams the latest 64 KiB and
fetches earlier pages through ``GET /api/logs/history?topic=app_log`` or
``topic=server_log:<name>`` using ``before`` and ``file_id`` cursors.
