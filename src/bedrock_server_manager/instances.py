_settings = None
_manager = None
_plugin_manager = None


def get_settings_instance():
    global _settings
    if _settings is None:
        from .config.settings import Settings

        _settings = Settings()
    return _settings


def get_manager_instance():
    global _manager
    if _manager is None:
        from bedrock_server_manager.core.manager import BedrockServerManager

        _manager = BedrockServerManager()
    return _manager


def get_plugin_manager_instance():
    global _plugin_manager
    if _plugin_manager is None:
        from .plugins.plugin_manager import PluginManager

        _plugin_manager = PluginManager()
    return _plugin_manager


_servers = {}


def get_server_instance(server_name: str):
    global _servers
    if _servers.get(server_name) is None:
        from bedrock_server_manager.core.bedrock_server import BedrockServer

        _servers[server_name] = BedrockServer(server_name)
    return _servers.get(server_name)
