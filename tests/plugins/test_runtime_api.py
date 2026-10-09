import pytest


async def test_runtime_lifecycle_positional_options_match_protocol(
    app_context, real_bedrock_server
):
    from bedrock_server_manager.plugins.api_bridge import create_app_api

    context = app_context
    api = create_app_api("example", context)
    async with api.runtime.server_lifecycle_manager(
        real_bedrock_server.server_name, False, False
    ):
        pass
    assert not await real_bedrock_server.is_running()
    with pytest.raises(TypeError):
        api.runtime.server_lifecycle_manager("server", False, app_context=context)
