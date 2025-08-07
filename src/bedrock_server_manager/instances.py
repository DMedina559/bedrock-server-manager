import warnings

_settings = None
_manager = None
_plugin_manager = None
_servers = {}


def get_settings_instance():
    warnings.warn(
        "get_settings_instance is deprecated and will be removed in a future version. "
        "Use the application context instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from .config.settings import Settings

    return Settings()


def get_manager_instance(settings_instance=None):
    warnings.warn(
        "get_manager_instance is deprecated and will be removed in a future version. "
        "Use the application context instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from .core import BedrockServerManager

    if settings_instance is None:
        settings_instance = get_settings_instance()

    return BedrockServerManager(settings_instance)


def get_plugin_manager_instance():
    """
    Returns a new instance of the PluginManager.

    .. deprecated:: 3.6.0
        This function is deprecated and will be removed in a future version.
        The PluginManager should be accessed from the application context
        (e.g., FastAPI request state or Click context) instead of being
        instantiated globally.
    """
    warnings.warn(
        "get_plugin_manager_instance is deprecated and will be removed in a future version. "
        "Use the application context instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from .plugins import PluginManager
    from .config import Settings

    settings = Settings()
    return PluginManager(settings)


def get_server_instance(server_name: str, settings_instance=None):
    warnings.warn(
        "get_server_instance is deprecated and will be removed in a future version. "
        "Use the application context instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # global _servers
    if _servers.get(server_name) is None:
        from .core import BedrockServer

        if settings_instance is None:
            settings_instance = get_settings_instance()

        _servers[server_name] = BedrockServer(
            server_name, settings_instance=settings_instance
        )
    return _servers.get(server_name)


def get_bedrock_process_manager(settings_instance=None):
    warnings.warn(
        "get_bedrock_process_manager is deprecated and will be removed in a future version. "
        "Use the application context instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from .core.bedrock_process_manager import BedrockProcessManager

    if settings_instance is None:
        settings_instance = get_settings_instance()

    return BedrockProcessManager(settings_instance=settings_instance)
