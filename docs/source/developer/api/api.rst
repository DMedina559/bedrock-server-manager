.. Bedrock Server Manager API documentation index file

API Documentation
=================

The functions listed in this part represent the primary, high-level interface for interacting with the Bedrock Server Manager. These APIs are used by all official components, including the Command-Line Interface (CLI), the Web, and the Plugin system.

These APIs provide a safe, consistent, and stable way to manage servers and the application itself.

Each data API accepts a Pydantic request and returns its declared Pydantic response.
Invalid input fails validation before plugin events or side effects. Application
failures propagate as exceptions to Python callers; HTTP, WebSocket, and task
boundaries serialize them as error responses. Invalid API output is an internal
failure rather than an input validation error.

Server-scoped action responses include ``server_name`` for both completed and
skipped work. This identity is also retained in background task results. A skipped
response means the operation did not run because its operation lock was busy.
HTTP task acceptance (202) indicates scheduling; inspect the task's final result
or error to determine whether the operation completed.

``delete_server_data`` with ``stop_if_running=False`` raises
``ServerRunningError`` if the server is running, preserving its process and data.

.. note::
   **For Plugin Developers:**
   The ``self.api`` object in your plugin exposes these APIs for your usage. However, to ensure consistency and safety of user data, only a specific **subset** of these APIs are endorsed for plugin use. Please refer to the :doc:`../../plugins/plugin_apis` sections of the Plugins Docs for the full list of functions that are guaranteed to be stable and supported for plugins.


.. toctree::
   :maxdepth: 2
   :caption: Server Actions

   server

.. toctree::
   :maxdepth: 2
   :caption: Server Configuration

   allowlist
   ban
   install
   permissions
   properties
   settings

.. toctree::
   :maxdepth: 2
   :caption: Backup & Restore

   backup_restore

.. toctree::
   :maxdepth: 2
   :caption: Content Management

   world
   addon

.. toctree::
   :maxdepth: 2
   :caption: Plugin Management

   plugins

.. toctree::
   :maxdepth: 2
   :caption: Global Operations

   application
   diagnostics
   player

.. toctree::
   :maxdepth: 2
   :caption: System Functions

   system

.. toctree::
   :maxdepth: 2
   :caption: Web & Real-Time Messaging

   web
   websocket

.. toctree::
   :maxdepth: 2
   :caption: Miscellaneous

   misc

Result and failure contracts
----------------------------

Python API requests and responses use strict Pydantic models. Unknown fields
are rejected. Domain and infrastructure failures propagate to the transport
boundary, where the shared classifier selects a safe message, stable error
code, and HTTP status. Missing resources use 404, conflicting operations use
409, and unavailable dependencies use 503. Unexpected failures retain their
traceback in logs without exposing exception text to clients.

Batch operations report ``partial`` when some work fails and ``skipped`` when
there is no work. Backup and restore details contain typed component outcomes
(``completed``, ``skipped``, or ``failed``); failed components include structured
error information. Cleanup results distinguish deleted and retained paths from
failed deletions. A successful backup remains usable if retention cleanup fails.

WebSocket delivery results report targeted, sent, unavailable, and failed
connections. An absent recipient produces ``skipped`` rather than claiming
delivery. Player imports distinguish submitted, parsed, unique, and persisted
counts. Consumers must inspect these result fields before assuming every item
succeeded. Incomplete-operation errors retain validated partial results in
error details.

Task snapshots enforce status/result/error relationships. Service mutations
validate candidate records before persistence and publish in-memory state only
after the database transaction commits. Plugins that invoke asynchronous API
methods must await them; the API caller check runs in CI.

Configuration and recovery failures
-----------------------------------

Allowlist and permission mutations reject invalid existing JSON or invalid
records before writing. They preserve the original configuration for repair.
Release lookup failures propagate before update lifecycle changes, and service
status queries raise when a negative state cannot be verified.

Account mutations that commit before connection revocation fails raise an
incomplete-operation error. Its validated result identifies the account and
action, includes ``committed: true``, and describes the recovery failure. The
committed mutation must not be treated as rolled back.

Password request fields are masked secrets and accept nonempty values of at most
72 UTF-8 bytes, matching the password hashing limit. Player summaries and scan
results validate their counters against the corresponding lists or input counts.
