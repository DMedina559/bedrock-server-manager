Bedrock Server Core
===================

``BedrockServer`` owns server identity and coordinates runtime operations.
Game data operations use explicit components rather than mixin inheritance:

* ``server.process``: process handles, start/stop, commands and resource queries.
* ``server.configuration``: typed persisted snapshots and validated updates.
* ``server.properties``, ``server.allowlist``, ``server.permissions``: file access.
* ``server.worlds`` and ``server.addons``: world and pack operations.
* ``server.player_tracker``: incremental log consumers.
* ``server.backups``: backup, restore, listing and retention.
* ``server.paths``: immutable filesystem locations.

``get_status()`` reads effective status without persisting changes. The process
monitor calls ``reconcile_status()`` to publish observed transitions. The existing
plugin event and websocket delivery path is retained.

``get_summary_info()`` returns ``SummaryRecord``; API adapters serialize it.
Configuration reads do not register missing servers, and writes require state
and storage. Restart counters belong to ``BedrockProcessManager``.

.. autoclass:: bedrock_server_manager.BedrockServer
   :members:
   :show-inheritance:

Backup and restore
------------------

Backup and restore operations acquire the server operation lock. Configuration
copies share the file locks used by normal configuration mutations. Backup names
have unique suffixes; existing timestamp-only backups remain restorable.
Full backups include ``server.properties``, ``allowlist.json`` and
``permissions.json``. Individual configuration backups accept local filenames. Restores require a stopped server; API lifecycle handling
stops and restarts it when requested. Full restore applies properties before
selecting the matching world archive. Component failures are reported; a full
restore is not a transaction across all configuration files and the world.

.. autoclass:: bedrock_server_manager.core.server.backup_restore.ServerBackups
   :members:

Software operations
-------------------

Install, update, permission setup, and deletion are standalone operations.

.. automodule:: bedrock_server_manager.core.server.software
   :members: is_update_needed, install_or_update

.. automodule:: bedrock_server_manager.core.server.removal
   :members: set_filesystem_permissions, delete_all_data
