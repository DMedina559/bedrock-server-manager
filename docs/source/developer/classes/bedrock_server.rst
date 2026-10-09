.. Bedrock Server Manager Bedrock Server Core documentation file

Bedrock Server Core Documentation
=================================

.. autoclass:: bedrock_server_manager.BedrockServer
   :members:
   :undoc-members:
   :show-inheritance:
   :inherited-members: bedrock_server_manager.core.server.base_server_mixin.BedrockServerBaseMixin, bedrock_server_manager.core.server.installation_mixin.ServerInstallationMixin, bedrock_server_manager.core.server.state_mixin.ServerStateMixin, bedrock_server_manager.core.server.process_mixin.ServerProcessMixin, bedrock_server_manager.core.server.world_mixin.ServerWorldMixin, bedrock_server_manager.core.server.addon_mixin.ServerAddonMixin, bedrock_server_manager.core.server.backup_restore_mixin.ServerBackupMixin, bedrock_server_manager.core.server.player_mixin.ServerPlayerMixin
   :member-order: bysource

   .. automethod:: __init__

Software operations
-------------------

Install, update, permission setup, and deletion are standalone core operations.
They accept a ``BedrockServer`` instance; install and delete serialize through
its operation lock. Plugin-facing API request and response contracts are unchanged.

.. automodule:: bedrock_server_manager.core.server.software
   :members: is_update_needed, install_or_update

.. automodule:: bedrock_server_manager.core.server.removal
   :members: set_filesystem_permissions, delete_all_data
