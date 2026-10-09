import asyncio
import json
import threading

import pytest
from websockets.exceptions import ConnectionClosed

from bedrock_server_manager.utils.auth import create_access_token


async def authenticate(socket, context, user):
    token = await create_access_token(context, {"sub": user.username})
    await socket.send(json.dumps({"action": "authenticate", "token": token}))
    response = json.loads(await socket.recv())
    assert response["status"] == "success"


async def test_websocket_missing_auth_action(websocket_client):
    async with websocket_client() as socket:
        await socket.send(json.dumps({"action": "subscribe", "topic": "test"}))
        with pytest.raises(ConnectionClosed) as failure:
            await socket.recv()
        assert failure.value.rcvd.code == 1008


async def test_websocket_auth_timeout(websocket_client):
    async with websocket_client() as socket:
        with pytest.raises(ConnectionClosed) as failure:
            await socket.recv()
        assert failure.value.rcvd.code == 1008


async def test_websocket_auth_success_and_messaging(
    websocket_client, app_context, test_user
):
    async with websocket_client() as socket:
        await authenticate(socket, app_context, test_user)
        for action in ("subscribe", "unsubscribe"):
            await socket.send(json.dumps({"action": action, "topic": "test_topic"}))
            response = json.loads(await socket.recv())
            assert response["status"] == "success"
            assert "test_topic" in response["message"]
        await socket.send(json.dumps({"action": "foo", "topic": "bar"}))
        assert json.loads(await socket.recv())["error"]["code"] == "validation_error"
        await socket.send(json.dumps({"action": "subscribe"}))
        assert json.loads(await socket.recv())["status"] == "error"


async def test_websocket_auth_via_cookie(
    websocket_client, unauth_client, app_context, test_user
):
    token = await create_access_token(app_context, {"sub": test_user.username})
    unauth_client.cookies.set("access_token_cookie", token)
    async with websocket_client() as socket:
        await socket.send(json.dumps({"action": "authenticate"}))
        assert json.loads(await socket.recv())["status"] == "success"


async def test_websocket_providers_report_results_and_safe_failures(
    websocket_client, app_context, test_user
):
    async def sample_provider(data, topic):
        return {"response": f"hello {data.get('name')}", "topic": topic}

    async def error_provider():
        raise ValueError("Provider failure")

    manager = app_context.connection_manager
    manager.register_data_provider("sample", sample_provider)
    manager.register_data_provider("failing", error_provider)
    async with websocket_client() as socket:
        await authenticate(socket, app_context, test_user)
        for topic in ("unknown_topic", "sample", "failing"):
            await socket.send(
                json.dumps(
                    {
                        "action": "request",
                        "topic": topic,
                        "data": {"name": "World"},
                        "request_id": topic,
                    }
                )
            )
            response = json.loads(await socket.recv())
            assert response["request_id"] == topic
            if topic == "sample":
                assert response["data"] == {"response": "hello World", "topic": topic}
            else:
                assert response["status"] == "error"
                assert "Provider failure" not in json.dumps(response)


async def test_invalid_provider_data_keeps_connection_usable(
    websocket_client, app_context, test_user
):
    async def invalid():
        return {"value": float("nan")}

    app_context.connection_manager.register_data_provider("invalid", invalid)
    async with websocket_client() as socket:
        await authenticate(socket, app_context, test_user)
        await socket.send(
            json.dumps(
                {"action": "request", "topic": "invalid", "request_id": "same-id"}
            )
        )
        response = json.loads(await socket.recv())
        assert response["request_id"] == "same-id"
        assert response["error"]["code"] == "internal_error"
        await socket.send(json.dumps(["not", "a", "frame"]))
        assert json.loads(await socket.recv())["error"]["code"] == "validation_error"
        await socket.send(json.dumps({"action": "subscribe", "topic": "valid"}))
        assert json.loads(await socket.recv())["status"] == "success"


async def test_sync_provider_runs_off_the_application_loop(
    websocket_client, app_context, test_user
):
    def provider():
        return threading.get_ident()

    app_context.connection_manager.register_data_provider("thread", provider)
    async with websocket_client() as socket:
        await authenticate(socket, app_context, test_user)
        await socket.send(
            json.dumps({"action": "request", "topic": "thread", "request_id": "thread"})
        )
        assert json.loads(await socket.recv())["data"] != threading.get_ident()


async def test_task_subscription_replays_completed_owner_snapshot(
    websocket_client, app_context, test_user, dummy_server_zip, tmp_path, wait_for_task
):
    from bedrock_server_manager.api.install import install_new_server
    from bedrock_server_manager.api.models import InstallNewServerRequest

    archive = dummy_server_zip(target_dir=tmp_path)
    task_id = await app_context.task_manager.run_task(
        install_new_server,
        username=test_user.username,
        request=InstallNewServerRequest(
            server_name="replay", target_version="CUSTOM", server_zip_path=str(archive)
        ),
        app_context=app_context,
    )
    completed = await wait_for_task(app_context, task_id)
    async with websocket_client() as socket:
        await authenticate(socket, app_context, test_user)
        await socket.send(
            json.dumps({"action": "subscribe", "topic": f"task:{task_id}"})
        )
        assert json.loads(await socket.recv())["status"] == "success"
        async with asyncio.timeout(5):
            update = json.loads(await socket.recv())
        assert update["type"] == "task_update"
        assert update["topic"] == f"task:{task_id}"
        assert update["data"]["status"] == "completed"
        assert update["data"]["result"]["version"] == completed.result["version"]
        assert "username" not in update["data"]


async def test_task_subscription_does_not_replay_another_users_snapshot(
    websocket_client, app_context, test_user, wait_for_task
):
    task_id = await app_context.task_manager.run_task(lambda: "private", "other")
    await wait_for_task(app_context, task_id)
    async with websocket_client() as socket:
        await authenticate(socket, app_context, test_user)
        await socket.send(
            json.dumps({"action": "subscribe", "topic": f"task:{task_id}"})
        )
        assert json.loads(await socket.recv())["status"] == "success"
        await socket.send(json.dumps({"action": "subscribe", "topic": "next"}))
        async with asyncio.timeout(5):
            assert "next" in json.loads(await socket.recv())["message"]
