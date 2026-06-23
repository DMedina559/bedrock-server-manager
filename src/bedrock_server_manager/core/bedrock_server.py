# bedrock_server_manager/core/bedrock_server.py
"""Defines the main :class:`~.BedrockServer` class, which consolidates all server management functionalities.

This module provides the :class:`~.BedrockServer` class, serving as the central
entry point for managing and interacting with a single Minecraft Bedrock Server instance.
The :class:`~.BedrockServer` is constructed by inheriting from a collection of
specialized mixin classes (e.g., for process control, world management, backups),
each contributing a distinct set of features. This compositional approach promotes
code organization and modularity, allowing for clear separation of concerns.
"""

from typing import Any, Dict, Optional

from ..config.settings import Settings
from . import server


class BedrockServer(
    # The order of inheritance is important for Method Resolution Order (MRO).
    # More specific mixins should generally come before more general ones.
    # BedrockServerBaseMixin, providing foundational __init__, is typically last.
    server.ServerStateMixin,
    server.ServerProcessMixin,
    server.ServerInstallationMixin,
    server.ServerWorldMixin,
    server.ServerAddonMixin,
    server.ServerBackupMixin,
    server.ServerPlayerMixin,
    server.ServerAllowlistMixin,
    server.ServerPermissionsMixin,
    server.ServerPropertiesMixin,
    server.ServerInstallUpdateMixin,
    # Foundational BedrockServerBaseMixin is last to ensure its __init__ runs after
    # all other mixins have potentially set up their specific attributes.
    server.BedrockServerBaseMixin,
):
    """Represents and manages a single Minecraft Bedrock Server instance.

    This class is the primary interface for all server-specific operations within
    the Bedrock Server Manager. It consolidates a wide range of functionalities
    by inheriting from the various specialized mixin classes listed above. Each instance of
    :class:`~.BedrockServer` is tied to a unique server name and provides
    methods to control, configure, and maintain that server.

    The order of mixin inheritance is significant for Python's Method Resolution
    Order (MRO), ensuring that methods are overridden and extended correctly.
    The :class:`~.core.server.base_server_mixin.BedrockServerBaseMixin` provides
    core attributes and foundational initialization logic.

    Attributes:
        server_name (str): The unique name identifying this server instance.
        settings (:class:`~bedrock_server_manager.config.settings.Settings`):
            The application's global settings object.
        base_dir (str): The base directory where all server installation
            directories reside (from settings: ``paths.servers``).
        server_dir (str): The full path to this specific server's installation
            directory (e.g., ``<base_dir>/<server_name>``).
        app_config_dir (str): Path to the application's global configuration
            directory (from settings: ``_config_dir``).
        os_type (str): The current operating system, e.g., "Linux", "Windows".
        logger (:class:`logging.Logger`): A logger instance specific to this
            server instance.

    Note:
        Many other attributes related to specific functionalities (e.g., server state,
        process information, world data paths) are available from the inherited mixin classes.
        Refer to the documentation of individual mixins for more details.

    Key Methods (Illustrative list, grouped by typical functionality):

        Installation & Validation (from :class:`~.core.server.installation_mixin.ServerInstallationMixin`):
            - :meth:`~.core.server.installation_mixin.ServerInstallationMixin.is_installed`
            - :meth:`~.core.server.installation_mixin.ServerInstallationMixin.validate_installation`
            - :meth:`~.core.server.installation_mixin.ServerInstallationMixin.set_filesystem_permissions`
            - :meth:`~.core.server.installation_mixin.ServerInstallationMixin.delete_all_data`

        State Management (from :class:`~.core.server.state_mixin.ServerStateMixin`):
            - :meth:`~.core.server.state_mixin.ServerStateMixin.get_status`
            - :meth:`~.core.server.state_mixin.ServerStateMixin.get_version`
            - :meth:`~.core.server.state_mixin.ServerStateMixin.set_version`
            - :meth:`~.core.server.state_mixin.ServerStateMixin.get_world_name`
            - :meth:`~.core.server.state_mixin.ServerStateMixin.get_custom_config_value`
            - :meth:`~.core.server.state_mixin.ServerStateMixin.set_custom_config_value`

        Process Management (from :class:`~.core.server.process_mixin.ServerProcessMixin`):
            - :meth:`~.core.server.process_mixin.ServerProcessMixin.is_running`
            - :meth:`~.core.server.process_mixin.ServerProcessMixin.get_process_info`
            - :meth:`~.core.server.process_mixin.ServerProcessMixin.start`
            - :meth:`~.core.server.process_mixin.ServerProcessMixin.stop`
            - :meth:`~.core.server.process_mixin.ServerProcessMixin.send_command`

        World Management (from :class:`~.core.server.world_mixin.ServerWorldMixin`):
            - :meth:`~.core.server.world_mixin.ServerWorldMixin.export_world`
            - :meth:`~.core.server.world_mixin.ServerWorldMixin.import_world`
            - :meth:`~.core.server.world_mixin.ServerWorldMixin.delete_world`

        Addon Management (from :class:`~.core.server.addon_mixin.ServerAddonMixin`):
            - :meth:`~.core.server.addon_mixin.ServerAddonMixin.process_addon_file`
            - :meth:`~.core.server.addon_mixin.ServerAddonMixin.list_installed_addons`
            - :meth:`~.core.server.addon_mixin.ServerAddonMixin.export_addon`
            - :meth:`~.core.server.addon_mixin.ServerAddonMixin.remove_addon`

        Backup & Restore (from :class:`~.core.server.backup_restore_mixin.ServerBackupMixin`):
            - :meth:`~.core.server.backup_restore_mixin.ServerBackupMixin.backup_all_data`
            - :meth:`~.core.server.backup_restore_mixin.ServerBackupMixin.restore_all_data_from_latest`
            - :meth:`~.core.server.backup_restore_mixin.ServerBackupMixin.prune_server_backups`
            - :meth:`~.core.server.backup_restore_mixin.ServerBackupMixin.list_backups`

        Player Log Scanning (from :class:`~.core.server.player_mixin.ServerPlayerMixin`):
            - :meth:`~.core.server.player_mixin.ServerPlayerMixin.scan_log_for_players`

        Config File Management (from :class:`~.core.server.allowlist_mixin.ServerAllowlistMixin`, :class:`~.core.server.permissions_mixin.ServerPermissionsMixin`, and :class:`~.core.server.properties_mixin.ServerPropertiesMixin`):
            - :meth:`~.core.server.allowlist_mixin.ServerAllowlistMixin.get_allowlist`
            - :meth:`~.core.server.allowlist_mixin.ServerAllowlistMixin.add_to_allowlist`
            - :meth:`~.core.server.permissions_mixin.ServerPermissionsMixin.set_player_permission`
            - :meth:`~.core.server.properties_mixin.ServerPropertiesMixin.get_server_properties`
            - :meth:`~.core.server.properties_mixin.ServerPropertiesMixin.set_server_property`

        Installation & Updates (from :class:`~.core.server.install_update_mixin.ServerInstallUpdateMixin`):
            - :meth:`~.core.server.install_update_mixin.ServerInstallUpdateMixin.is_update_needed`
            - :meth:`~.core.server.install_update_mixin.ServerInstallUpdateMixin.install_or_update`

    Note:
        This is not an exhaustive list of all available methods. Many more specialized
        methods are accessible from the respective mixin classes. Please consult the
        documentation for each individual mixin for a comprehensive list of its capabilities.
    """

    def __init__(
        self, server_name: str, settings_instance: Optional[Settings] = None
    ) -> None:
        """Initializes a BedrockServer instance.

        This constructor is responsible for setting up a :class:`~.BedrockServer`
        object, which represents a specific Minecraft Bedrock server. It calls
        ``super().__init__(...)``, triggering the initialization methods of all
        inherited mixin classes according to Python's Method Resolution Order (MRO).
        This process starts with the first mixin in the inheritance list (currently
        :class:`~.core.server.state_mixin.ServerStateMixin`) and culminates with
        :class:`~.core.server.base_server_mixin.BedrockServerBaseMixin`, which
        establishes fundamental server attributes.

        Args:
            server_name (str): The unique name for this server instance. This name
                is also used as the directory name for the server's files under
                the application's base server directory (defined by
                ``paths.servers_base_dir`` in settings).
            settings_instance (:class:`~bedrock_server_manager.config.settings.Settings`):
                An instance of the application's global :class:`~bedrock_server_manager.config.settings.Settings`
                object. This is a required dependency.
        """
        super().__init__(
            server_name=server_name,
            settings_instance=settings_instance,
        )
        self.logger.info(
            f"BedrockServer instance '{self.server_name}' fully initialized and ready for operations."
        )

    def get_summary_info(self) -> Dict[str, Any]:
        """Returns a generic summary of the server's current status and state.

        This method provides lightweight data suitable for list views and general
        snapshots, including details like installation status, running status,
        version, and active players.

        Returns:
            Dict[str, Any]: A dictionary containing a basic summary of the server.

            Key keys include:
                - ``"name"`` (str): The unique name of the server.
                - ``"status"`` (str): A textual description of the server's
                  current status (e.g., "Running", "Stopped", "Not Installed").
                - ``"version"`` (str): The installed version of the Bedrock server,
                  or "N/A".
                - ``"player_count"`` (int): Current number of active players.
                - ``"players"`` (List[Dict[str, Any]]): List of connected player details.
        """
        self.logger.debug(f"Gathering summary info for server '{self.server_name}'.")

        summary = {
            "name": self.server_name,
            "status": self.get_status(),
            "version": self.get_version(),
            "player_count": self.player_count,
            "players": getattr(self, "players", []),
        }

        return summary
