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
or complete request/response payloads. Errors should include useful context and a
traceback at the boundary that handles the failure; avoid repeating the same error
through every layer. ``log_operation_error`` classifies expected rejections and
retains reporting ownership when the same exception is re-raised or explicitly
wrapped with ``raise ... from ...``. Independent fallback failures remain separate.

The console uses concise level/message output. At INFO and higher, tracebacks stay
in the timestamped application log; DEBUG also shows them in the console. Application
logs streamed to the web UI retain timestamps, logger names, server context, and
tracebacks. Common credential representations are redacted, and control characters
in messages are escaped. This is defense in depth, not a reason to log sensitive data.

SQL and HTTP dependency logs retain warnings and errors while their routine output
is suppressed, including at DEBUG. Database error messages hide bound parameters.

Logging setup preserves host handlers, replaces only application-owned handlers,
and updates their levels together. HTTP access and routine WebSocket connection
records appear only at DEBUG. Uvicorn inherits the application logging level.
Each session keeps its active file plus up to four 10 MiB rotated files; startup
retains five sessions and removes their rotated files together. The web viewer
handles rotation and streams at most 64 KiB per topic per polling cycle.
Retrying process-monitor, log-stream, and resource-monitor failures are reported on the first failure,
when the error changes, and at most once per minute for the same error; recovery is
reported once.

The log viewer loads the latest 64 KiB first. Scrolling up requests earlier pages
through ``GET /api/logs/history?topic=app_log`` or ``topic=server_log:<name>``.
Pass the previous page's ``start`` as ``before`` and its ``file_id`` to continue.
Pages contain ``data``, byte offsets ``start``/``end``, ``file_id``, and ``has_more``.
Live ``log_update`` frames retain their string ``data`` and add the same offsets
and file identity so viewers can merge overlapping history and live output.
File replacement or truncation invalidates stale history cursors with HTTP 409.
Application history requires an administrator; server history requires a moderator.
