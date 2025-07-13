# bedrock_server_manager/core/server/__init__.py
import platform

from .addon_mixin import ServerAddonMixin
from .backup_restore_mixin import ServerBackupMixin
from .base_server_mixin import BedrockServerBaseMixin
from .config_management_mixin import ServerConfigManagementMixin
from .installation_mixin import ServerInstallationMixin
from .install_update_mixin import ServerInstallUpdateMixin
from .player_mixin import ServerPlayerMixin
from .process_mixin import ServerProcessMixin
from .state_mixin import ServerStateMixin
from .world_mixin import ServerWorldMixin

if platform.system() == "Windows":
    from .windows_service_mixin import ServerWindowsServiceMixin
else:
    # If not Windows, we don't need the Windows service mixin
    class ServerWindowsServiceMixin:
        """Placeholder for Windows service mixin on non-Windows systems."""

        pass


if platform.system() == "Linux":
    from .systemd_mixin import ServerSystemdMixin
else:
    # If not Linux, we don't need the systemd mixin
    class ServerSystemdMixin:
        """Placeholder for systemd mixin on non-Linux systems."""

        pass


__all__ = [
    "ServerAddonMixin",
    "ServerBackupMixin",
    "BedrockServerBaseMixin",
    "ServerConfigManagementMixin",
    "ServerInstallationMixin",
    "ServerInstallUpdateMixin",
    "ServerPlayerMixin",
    "ServerProcessMixin",
    "ServerStateMixin",
    "ServerSystemdMixin",
    "ServerWindowsServiceMixin",
    "ServerWorldMixin",
]
