from bedrock_server_manager.config.settings import Settings


_settings = None
_manager = None


def get_settings_instance() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def get_manager_instance():
    global _manager
    if _manager is None:
        from bedrock_server_manager.core.manager import BedrockServerManager

        _manager = BedrockServerManager()
    return _manager


_servers = {}


def get_server_instance(server_name: str):
    global _servers
    if _servers.get(server_name) is None:
        from bedrock_server_manager.core.bedrock_server import BedrockServer

        _servers[server_name] = BedrockServer(server_name)
    return _servers.get(server_name)
