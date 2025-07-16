_settings = None
_manager = None
_plugin_manager = None
_servers = {}


def get_settings_instance():
    from .config.settings import Settings

    return Settings()


def get_manager_instance():
    from .core import BedrockServerManager

    return BedrockServerManager()


def get_plugin_manager_instance():
    """
    Returns the singleton instance of the PluginManager.
    """
    from .plugins import PluginManager

    return PluginManager()


def get_server_instance(server_name: str):
    # global _servers
    if _servers.get(server_name) is None:
        from .core import BedrockServer

        _servers[server_name] = BedrockServer(server_name)
    return _servers.get(server_name)


def get_bedrock_process_manager():
    from .core.bedrock_process_manager import BedrockProcessManager

    return BedrockProcessManager()
