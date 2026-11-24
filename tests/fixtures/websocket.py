"""Real HTTP/WebSocket transport sharing the application's asyncio loop."""

import asyncio
import json
import socket
from collections import deque
from contextlib import asynccontextmanager

import pytest_asyncio
import uvicorn
from websockets.asyncio.client import connect

from bedrock_server_manager.web.auth import create_access_token


@pytest_asyncio.fixture
async def websocket_client(running_app, unauth_client):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            running_app,
            lifespan="off",
            access_log=False,
            log_level="warning",
            proxy_headers=False,
        )
    )
    task = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        async with asyncio.timeout(5):
            while not server.started:
                if task.done():
                    task.result()
                    raise RuntimeError("WebSocket server exited before startup")
                await asyncio.sleep(0.01)

        @asynccontextmanager
        async def open_socket(path="/ws", additional_headers=None):
            cookies = "; ".join(
                f"{name}={value}" for name, value in unauth_client.cookies.items()
            )
            headers = dict(additional_headers or {})
            if cookies:
                headers["Cookie"] = cookies
                headers.setdefault("Origin", f"http://127.0.0.1:{port}")
            async with connect(
                f"ws://127.0.0.1:{port}{path}", additional_headers=headers
            ) as connection:
                yield connection

        yield open_socket
    finally:
        server.should_exit = True
        try:
            await asyncio.wait_for(task, 5)
        finally:
            listener.close()


@pytest_asyncio.fixture
async def subscribed_socket(websocket_client, app_context, test_admin_user):
    @asynccontextmanager
    async def subscribe(*topics):
        # Prepare the database-backed credential before the server starts its
        # first-frame authentication deadline, matching a real signed-in client.
        token = await create_access_token(
            app_context, {"sub": test_admin_user.username}
        )
        async with websocket_client() as connection:
            raw_recv = connection.recv
            buffered = deque()

            async def recv(*args, **kwargs):
                if buffered:
                    return buffered.popleft()
                return await raw_recv(*args, **kwargs)

            async with asyncio.timeout(5):
                await connection.send(
                    json.dumps({"action": "authenticate", "token": token})
                )
                reply = json.loads(await raw_recv())
                assert reply["status"] == "success", reply
            for topic in topics:
                async with asyncio.timeout(5):
                    await connection.send(
                        json.dumps({"action": "subscribe", "topic": topic})
                    )
                    while True:
                        raw = await raw_recv()
                        message = json.loads(raw)
                        if "status" in message and "topic" not in message:
                            assert message["status"] == "success", (topic, message)
                            break
                        buffered.append(raw)
            connection.recv = recv
            yield connection

    return subscribe
