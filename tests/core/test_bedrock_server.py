from bedrock_server_manager.core.bedrock_server import BedrockServer


def test_bedrock_server_composition(app_context):
    """Test that the BedrockServer correctly inherits all properties and methods from mixins."""
    server = BedrockServer(server_name="composed_server", app_context=app_context)

    # Check Base
    assert server.server_name == "composed_server"

    # Check Install/Update mixin
    assert hasattr(server, "install_or_update")

    # Check Properties mixin
    assert hasattr(server, "get_server_property")

    # Check Allowlist/Permissions mixin
    assert hasattr(server, "get_allowlist")
    assert hasattr(server, "get_formatted_permissions")

    # Check World/Backup mixin
    assert hasattr(server, "backup_all_data")
    assert hasattr(server, "has_world_icon")

    # Check Process/State mixin
    assert hasattr(server, "start")
    assert hasattr(server, "get_status")

    # Check Player/Addon mixin
    assert hasattr(server, "update_online_players")
    assert hasattr(server, "list_installed_addons")
