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
