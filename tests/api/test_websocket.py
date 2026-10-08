import asyncio
import json

from bedrock_server_manager.plugins.api_bridge import create_app_api
from bedrock_server_manager.utils.auth import create_access_token


async def test_plugin_websocket_api_delivers_real_frames(
    websocket_client, app_context, test_user
):
    api = create_app_api("integration", app_context)
    token = await create_access_token(app_context, {"sub": test_user.username})
    async with websocket_client() as socket:
        await socket.send(json.dumps({"action": "authenticate", "token": token}))
        assert json.loads(await socket.recv())["status"] == "success"
        await socket.send(json.dumps({"action": "subscribe", "topic": "integration"}))
        assert json.loads(await socket.recv())["status"] == "success"
        response = await api.websocket.websocket_broadcast(
            {"topic": "integration", "data": {"value": 1}}
        )
        assert response.status == "success"
        async with asyncio.timeout(5):
            frame = json.loads(await socket.recv())
        assert frame == {
            "type": "broadcast",
            "topic": "integration",
            "data": {"value": 1},
        }
        await api.websocket.websocket_send_to_user(
            {"username": test_user.username, "data": {"value": 2}}
        )
        async with asyncio.timeout(5):
            assert json.loads(await socket.recv()) == {"value": 2}
        client_id = next(iter(app_context.connection_manager.active_connections))
        await api.websocket.websocket_send_to_client(
            {"client_id": client_id, "data": {"value": 3}}
        )
        async with asyncio.timeout(5):
            assert json.loads(await socket.recv()) == {"value": 3}


async def test_plugin_provider_registration_serves_actual_requests(
    websocket_client, app_context, test_user, plugin_factory
):
    plugin = await plugin_factory(
        "provider",
        "from bedrock_server_manager import PluginBase\nclass Provider(PluginBase):\n    version = '1.0'\n",
    )

    def provider():
        return {"value": 7}

    await plugin.api.runtime.register_data_provider("integration", provider)
    token = await create_access_token(app_context, {"sub": test_user.username})
    async with websocket_client() as socket:
        await socket.send(json.dumps({"action": "authenticate", "token": token}))
        assert json.loads(await socket.recv())["status"] == "success"
        await socket.send(
            json.dumps({"action": "request_data", "topic": "integration"})
        )
        frame = json.loads(await socket.recv())
        assert frame["data"] == {"value": 7}
        await plugin.api.websocket.websocket_unregister_data_provider(
            {"topic": "integration"}
        )
        await socket.send(
            json.dumps({"action": "request_data", "topic": "integration"})
        )
        assert json.loads(await socket.recv())["status"] == "error"
