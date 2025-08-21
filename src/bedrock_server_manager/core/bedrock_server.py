# bedrock_server_manager/core/bedrock_server.py
"""Defines the main :class:`~.BedrockServer` class, which consolidates all server management functionalities.

This module provides the :class:`~.BedrockServer` class, serving as the central
entry point for managing and interacting with a single Minecraft Bedrock Server instance.
The :class:`~.BedrockServer` is constructed by inheriting from a collection of
specialized mixin classes (e.g., for process control, world management, backups),
each contributing a distinct set of features. This compositional approach promotes
code organization and modularity, allowing for clear separation of concerns.
"""
from typing import Dict, Any

# Import all the mixin classes that will be combined to form the BedrockServer.
from . import server
from ..config.settings import Settings
from ..error import FileOperationError, ConfigParseError


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
    server.ServerConfigManagementMixin,
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
            - :meth:`~.core.server.world_mixin.ServerWorldMixin.export_world_directory_to_mcworld`
            - :meth:`~.core.server.world_mixin.ServerWorldMixin.import_active_world_from_mcworld`
            - :meth:`~.core.server.world_mixin.ServerWorldMixin.delete_active_world_directory`

        Addon Management (from :class:`~.core.server.addon_mixin.ServerAddonMixin`):
            - :meth:`~.core.server.addon_mixin.ServerAddonMixin.process_addon_file`
            - :meth:`~.core.server.addon_mixin.ServerAddonMixin.list_world_addons`
            - :meth:`~.core.server.addon_mixin.ServerAddonMixin.export_addon`
            - :meth:`~.core.server.addon_mixin.ServerAddonMixin.remove_addon`

        Backup & Restore (from :class:`~.core.server.backup_restore_mixin.ServerBackupMixin`):
            - :meth:`~.core.server.backup_restore_mixin.ServerBackupMixin.backup_all_data`
            - :meth:`~.core.server.backup_restore_mixin.ServerBackupMixin.restore_all_data_from_latest`
            - :meth:`~.core.server.backup_restore_mixin.ServerBackupMixin.prune_server_backups`
            - :meth:`~.core.server.backup_restore_mixin.ServerBackupMixin.list_backups`

        Player Log Scanning (from :class:`~.core.server.player_mixin.ServerPlayerMixin`):
            - :meth:`~.core.server.player_mixin.ServerPlayerMixin.scan_log_for_players`

        Config File Management (from :class:`~.core.server.config_management_mixin.ServerConfigManagementMixin`):
            - :meth:`~.core.server.config_management_mixin.ServerConfigManagementMixin.get_allowlist`
            - :meth:`~.core.server.config_management_mixin.ServerConfigManagementMixin.add_to_allowlist`
            - :meth:`~.core.server.config_management_mixin.ServerConfigManagementMixin.set_player_permission`
            - :meth:`~.core.server.config_management_mixin.ServerConfigManagementMixin.get_server_properties`
            - :meth:`~.core.server.config_management_mixin.ServerConfigManagementMixin.set_server_property`

        Installation & Updates (from :class:`~.core.server.install_update_mixin.ServerInstallUpdateMixin`):
            - :meth:`~.core.server.install_update_mixin.ServerInstallUpdateMixin.is_update_needed`
            - :meth:`~.core.server.install_update_mixin.ServerInstallUpdateMixin.install_or_update`

    Note:
        This is not an exhaustive list of all available methods. Many more specialized
        methods are accessible from the respective mixin classes. Please consult the
        documentation for each individual mixin for a comprehensive list of its capabilities.
    """

    def __init__(self, server_name: str, settings_instance: Settings = None) -> None:
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

    def __repr__(self) -> str:
        """Provides an unambiguous, developer-friendly string representation of the instance.

        This representation is primarily useful for debugging and logging purposes.
        It includes key identifiers of the server instance such as its name,
        operating system type, installation directory, and the manager executable path.

        Returns:
            str: A string representation of the :class:`~.BedrockServer` instance.
        """
        return (
            f"<BedrockServer(name='{self.server_name}', os='{self.os_type}', "
            f"dir='{self.server_dir}')>"
        )

    def get_summary_info(self) -> Dict[str, Any]:
        """Aggregates and returns a comprehensive summary of the server's current state.

        This method gathers information from various other status and configuration
        methods of the :class:`~.BedrockServer` instance and consolidates it into a
        single dictionary. This is particularly useful for API endpoints or UI
        displays that require a snapshot of the server's status.

        The method attempts to fetch all pieces of information gracefully, logging
        warnings for parts that cannot be retrieved (e.g., process details if the
        server isn't running, or world name if not installed) and providing
        default/error values in such cases.

        Returns:
            Dict[str, Any]: A dictionary containing a summary of the server.

            Key keys include:

                - ``"name"`` (str): The unique name of the server.
                - ``"server_directory"`` (str): Absolute path to the server's
                  installation directory.
                - ``"is_installed"`` (bool): ``True`` if the server files appear
                  to be installed, ``False`` otherwise.
                - ``"status"`` (str): A textual description of the server's
                  current status (e.g., "Running", "Stopped", "Not Installed").
                  Derived from :meth:`~.core.server.state_mixin.ServerStateMixin.get_status`.
                - ``"is_actually_running_process"`` (bool): ``True`` if a server
                  process is currently running, based on :meth:`~.core.server.process_mixin.ServerProcessMixin.is_running`.
                - ``"process_details"`` (Optional[Dict[str, Any]]): Information about
                  the running process (e.g., PID, CPU, memory) if available,
                  otherwise ``None``. From :meth:`~.core.server.process_mixin.ServerProcessMixin.get_process_info`.
                - ``"version"`` (str): The installed version of the Bedrock server,
                  or "N/A". From :meth:`~.core.server.state_mixin.ServerStateMixin.get_version`.
                - ``"world_name"`` (str): The name of the currently active world,
                  "N/A" if not determinable, or an error string if reading fails.
                  From :meth:`~.core.server.state_mixin.ServerStateMixin.get_world_name`.
                - ``"has_world_icon"`` (bool): ``True`` if a ``world_icon.jpeg``
                  exists for the active world. From :meth:`~.core.server.world_mixin.ServerWorldMixin.has_world_icon`.
                - ``"os_type"`` (str): The operating system type (e.g., "Linux", "Windows").
                - ``"systemd_service_file_exists"`` (Optional[bool]): (Linux-only)
                  ``True`` if a systemd service file exists, ``False`` if not,
                  ``None`` if not Linux or check fails.
                - ``"systemd_service_enabled"`` (Optional[bool]): (Linux-only)
                  ``True`` if systemd service is enabled, ``False`` if not,
                  ``None`` if not applicable.
                - ``"systemd_service_active"`` (Optional[bool]): (Linux-only)
                  ``True`` if systemd service is active, ``False`` if not,
                  ``None`` if not applicable.

        """
        self.logger.debug(f"Gathering summary info for server '{self.server_name}'.")

        # Safely get process information.
        proc_details = None
        is_server_running = False
        try:
            is_server_running = self.is_running()
            if is_server_running:
                proc_details = self.get_process_info()
        except Exception as e_proc:
            self.logger.warning(
                f"Could not get process status/info for '{self.server_name}': {e_proc}"
            )

        # Safely get world information.
        world_name_val = "N/A"
        has_icon_val = False
        if self.is_installed():
            try:
                world_name_val = self.get_world_name()
                has_icon_val = self.has_world_icon()
            except (FileOperationError, ConfigParseError) as e_world:
                self.logger.warning(
                    f"Error reading world name/icon for '{self.server_name}': {e_world}"
                )
                world_name_val = f"Error ({type(e_world).__name__})"

        # Build the main summary dictionary.
        summary = {
            "name": self.server_name,
            "server_directory": self.server_dir,
            "is_installed": self.is_installed(),
            "status": self.get_status(),
            "is_actually_running_process": is_server_running,
            "process_details": proc_details,
            "version": self.get_version(),
            "world_name": world_name_val,
            "has_world_icon": has_icon_val,
            "os_type": self.os_type,
            "player_count": self.player_count,
        }

        return summary
