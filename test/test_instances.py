import pytest
from bedrock_server_manager.instances import (
    get_settings_instance,
    get_manager_instance,
    get_server_instance,
    get_bedrock_process_manager,
)
from bedrock_server_manager.context import AppContext


def test_get_settings_instance(app_context: AppContext):
    """Tests that get_settings_instance returns the correct settings instance from the context."""
    with pytest.deprecated_call():
        settings = get_settings_instance()
    assert settings is app_context.settings


def test_get_manager_instance(app_context: AppContext):
    """Tests that get_manager_instance returns the correct manager instance from the context."""
    with pytest.deprecated_call():
        manager = get_manager_instance()
    assert manager is app_context.manager


def test_get_server_instance(app_context: AppContext):
    """Tests that get_server_instance returns the correct server instance from the context."""
    with pytest.deprecated_call():
        server = get_server_instance("test_server")
    assert server is app_context.get_server("test_server")


def test_get_bedrock_process_manager(app_context: AppContext):
    """Tests that get_bedrock_process_manager returns the correct bedrock_process_manager instance from the context."""
    with pytest.deprecated_call():
        process_manager = get_bedrock_process_manager()
    assert process_manager is app_context.bedrock_process_manager
