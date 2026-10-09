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
        """str: The full, absolute path to this server's Bedrock executable.
        Constructed by joining `self.server_dir` and `self.bedrock_executable_name`.
        """
        return os.path.join(self.server_dir, self.bedrock_executable_name)

    @property
    def server_log_path(self) -> str:
        """str: The expected absolute path to the server's main output log file.
        Typically ``<server_dir>/server_output.txt``.
        """
        return os.path.join(self.server_dir, "server_output.txt")

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
        """str: The absolute path to this server instance's dedicated configuration subdirectory.
        This is usually ``<app_config_dir>/<server_name>/``, and is intended
        to store server-specific configuration files, PID files, etc.
        The directory itself is not created by this property.
        """
        return os.path.join(self.app_config_dir, self.server_name)
