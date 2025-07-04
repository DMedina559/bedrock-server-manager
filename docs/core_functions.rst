This section covers the different layers of the Bedrock Server Manager's architecture, from the high-level Application API to the low-level internal functions.

Public APIs
-----------
The functions listed in this part represent the primary, high-level interface for interacting with the Bedrock Server Manager. These APIs are used by all official components, including the Command-Line Interface (CLI), the Web, and the Plugin system.

These APIs provide a safe, consistent, and stable way to manage servers and the application itself.

.. note::
   **For Plugin Developers:**
   The ``self.api`` object in your plugin exposes these APIs for your usage. However, to ensure consistency and safety of user data, only a specific **subset** of these APIs are endorsed for plugin use. Please refer to the **`Availiable APIs`** sections of the Plugins Docs for the full list of functions that are guaranteed to be stable and supported for plugins.

.. toctree::
   :maxdepth: 2
   :caption: APIs

   api

Public PyClasses
----------------
These classes are the primary foundation for the Bedrock Server Manager application, indvidual Bedrock Dedicated Servers, and the global Settings used through out the application. 

While its not generally recommended to use these classes directly, they are available for use, and could provide a for more advanced processes.

.. note::
   **Before using these classes**, consider the Public APIs section above, as these classes are used by the public APIs, and using the public APIs is the recommended way to interact with the Bedrock Server Manager in a **safe** and **consistent** way.

.. toctree::
   :maxdepth: 2
   :caption: Classes

   public_classes

Backend Functions (For Internal Development)
--------------------------------------------

.. warning::
   The modules documented below are the internal engine of the Bedrock Server Manager. They are **not** part of the public API, are subject to change without notice, and **must not** be used directly by plugins. Doing so will result in a broken plugin after future updates.

This documentation is provided mostly for contributors working on the core application, or curious into its underlying functions not listed else where.


System Functions
-----------------
.. automodule:: bedrock_server_manager.core.system.base
   :members:
   :undoc-members:
   :exclude-members: PSUTIL_AVAILABLE

.. automodule:: bedrock_server_manager.core.system.process
   :members:
   :undoc-members:
   :exclude-members: PSUTIL_AVAILABLE

Platform-Specific Functions
---------------------------

.. automodule:: bedrock_server_manager.core.system.linux
   :members:
   :undoc-members:
   :exclude-members: BEDROCK_EXECUTABLE_NAME, PIPE_NAME_TEMPLATE

.. automodule:: bedrock_server_manager.core.system.windows
   :members:
   :undoc-members:
   :exclude-members: BEDROCK_EXECUTABLE_NAME, PIPE_NAME_TEMPLATE

Miscellaneous Functions
-----------------------
.. automodule:: bedrock_server_manager.core.utils
   :members:
   :undoc-members:

.. autofunction:: bedrock_server_manager.core.downloader.prune_old_downloads

Platform-Specific Task Schedulers
---------------------------------
.. automodule:: bedrock_server_manager.core.system.task_scheduler
   :members:
   :undoc-members:




