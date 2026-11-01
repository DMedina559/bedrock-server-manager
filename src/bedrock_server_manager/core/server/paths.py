import glob
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ServerPaths:
    server_name: str
    base_dir: str
    app_config_dir: str
    os_type: str

    @property
    def server_dir(self) -> str:
        return os.path.join(self.base_dir, self.server_name)

    @property
    def bedrock_executable_name(self) -> str:
        """str: The platform-specific name of the Bedrock server executable.
        Returns "bedrock_server.exe" on Windows, "bedrock_server" otherwise.
        """
        return "bedrock_server.exe" if self.os_type == "Windows" else "bedrock_server"

    @property
    def bedrock_executable_path(self) -> str:
        """str: The full, absolute path to this server's Bedrock executable. Constructed
        by joining ``self.server_dir`` and ``self.bedrock_executable_name``.
        """
        return os.path.join(self.server_dir, self.bedrock_executable_name)

    @property
    def server_log_dir(self) -> str:
        """str: The absolute path to this server instance's dedicated log directory.
        This is ``<app_config_dir>/logs/servers/<server_name>/``.
        """
        return os.path.join(self.app_config_dir, "logs", "servers", self.server_name)

    @property
    def server_log_path(self) -> str:
        """str: The expected absolute path to the server's main output log file.
        Resolves the most recent ``<server_name>_*.log`` (or ``server_output.log``)
        in ``<app_config_dir>/logs/servers/<server_name>/``.
        """
        log_dir = self.server_log_dir
        if os.path.isdir(log_dir):
            try:
                candidates = glob.glob(
                    os.path.join(log_dir, f"{glob.escape(self.server_name)}_*.log")
                )
                fixed_log = os.path.join(log_dir, "server_output.log")
                if os.path.isfile(fixed_log):
                    candidates.append(fixed_log)
                if candidates:
                    return max(candidates, key=os.path.getmtime)
            except OSError:
                pass
        return os.path.join(log_dir, "server_output.log")

    @property
    def server_properties_path(self) -> str:
        """str: The absolute path to this server's ``server.properties`` file."""
        return os.path.join(self.server_dir, "server.properties")

    @property
    def allowlist_json_path(self) -> str:
        """str: The absolute path to this server's ``allowlist.json`` file."""
        return os.path.join(self.server_dir, "allowlist.json")

    @property
    def permissions_json_path(self) -> str:
        """str: The absolute path to this server's ``permissions.json`` file."""
        return os.path.join(self.server_dir, "permissions.json")

    @property
    def server_config_dir(self) -> str:
        """str: The absolute path to this server instance's dedicated runtime/configuration subdirectory.
        This is ``<app_config_dir>/runtime/servers/<server_name>/``, and is intended
        to store server-specific runtime and PID files.
        The directory itself is not created by this property.
        """
        return os.path.join(self.app_config_dir, "runtime", "servers", self.server_name)
