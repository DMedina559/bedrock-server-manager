Core Internals
==============

This section describes the core internal classes and logic of the Bedrock Server Manager.

Main Classes
------------

.. autoclass:: bedrock_server_manager.core.bedrock_server.BedrockServer
   :members:
   :undoc-members:
   :show-inheritance:
   :inherited-members: bedrock_server_manager.core.server.base_server_mixin.BedrockServerBaseMixin, bedrock_server_manager.core.server.installation_mixin.ServerInstallationMixin, bedrock_server_manager.core.server.state_mixin.ServerStateMixin, bedrock_server_manager.core.server.process_mixin.ServerProcessMixin, bedrock_server_manager.core.server.world_mixin.ServerWorldMixin, bedrock_server_manager.core.server.addon_mixin.ServerAddonMixin, bedrock_server_manager.core.server.backup_restore_mixin.ServerBackupMixin, bedrock_server_manager.core.server.systemd_mixin.ServerSystemdMixin, bedrock_server_manager.core.server.player_mixin.ServerPlayerMixin, bedrock_server_manager.core.server.windows_service_mixin.ServerWindowsServiceMixin, bedrock_server_manager.core.server.config_management_mixin.ServerConfigManagementMixin, bedrock_server_manager.core.server.install_update_mixin.ServerInstallUpdateMixin
   :member-order: bysource

   .. automethod:: __init__

.. autoclass:: bedrock_server_manager.core.manager.BedrockServerManager
   :members:
   :undoc-members:
   :show-inheritance:
   :member-order: bysource

   .. automethod:: __init__

Core Utilities
--------------

.. automodule:: bedrock_server_manager.core.utils
   :members:
   :undoc-members:

.. automodule:: bedrock_server_manager.core.downloader
   :members:
   :undoc-members:

System Interaction
------------------
This covers platform specific logic. For a higher-level API for tasks like service management, see the :mod:`bedrock_server_manager.api.system` module.

.. automodule:: bedrock_server_manager.core.system.base
   :members:
   :undoc-members:

.. automodule:: bedrock_server_manager.core.system.linux
   :members:
   :undoc-members:

.. automodule:: bedrock_server_manager.core.system.windows
   :members:
   :undoc-members:

.. automodule:: bedrock_server_manager.core.system.process
   :members:
   :undoc-members:

.. automodule:: bedrock_server_manager.core.system.task_scheduler
   :members:
   :undoc-members:
   :show-inheritance:
