Windows service host
====================

``bedrock_server_manager.web.windows_service`` owns the Windows SCM host.
It imports pywin32 and is available only on Windows. SCM stop requests signal
WebRuntime and wait for normal cleanup; intentional HTTP shutdown exits through
the same host. Runtime failures are reported as service failures.

Use CLI service configuration rather than instantiating this platform host from
plugins. See :doc:`../../../extras/web_runtime` for supervision behavior.
