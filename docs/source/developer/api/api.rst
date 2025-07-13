.. Bedrock Server Manager API documentation index file

API Documentation
=================

The functions listed in this part represent the primary, high-level interface for interacting with the Bedrock Server Manager. These APIs are used by all official components, including the Command-Line Interface (CLI), the Web, and the Plugin system.

These APIs provide a safe, consistent, and stable way to manage servers and the application itself.

.. note::
   **For Plugin Developers:**
   The ``self.api`` object in your plugin exposes these APIs for your usage. However, to ensure consistency and safety of user data, only a specific **subset** of these APIs are endorsed for plugin use. Please refer to the :doc:`../../plugins/plugin_apis` sections of the Plugins Docs for the full list of functions that are guaranteed to be stable and supported for plugins.


.. toctree::
   :maxdepth: 2
   :caption: Server Actions

   server

.. toctree::
   :maxdepth: 2
   :caption: Server Install & Config

   server_install_config

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
   :caption: Web Server

   web

.. toctree::
   :maxdepth: 2
   :caption: Miscellaneous

   misc
   info
   utils

.. toctree::
   :maxdepth: 2
   :caption: Task Scheduler

   task_scheduler