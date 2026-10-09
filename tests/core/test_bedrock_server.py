from bedrock_server_manager.core.bedrock_server import BedrockServer


def test_bedrock_server_components(app_context):
    server = BedrockServer(
        "composed_server",
        settings=app_context.settings,
        app_context=app_context,
        state=app_context.state,
        storage=app_context.storage,
    )
    assert server.server_name == "composed_server"
    for component in (
        server.process,
        server.configuration,
        server.properties,
        server.allowlist,
        server.permissions,
        server.worlds,
        server.addons,
        server.backups,
        server.player_tracker,
    ):
        assert component.server is server
    assert not hasattr(server, "install_or_update")
