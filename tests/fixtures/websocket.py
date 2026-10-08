"""Real HTTP/WebSocket transport sharing the application's asyncio loop."""

import asyncio
import socket
from contextlib import asynccontextmanager

import pytest_asyncio
import uvicorn
from websockets.asyncio.client import connect


@pytest_asyncio.fixture
async def websocket_client(running_app, unauth_client):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            running_app, lifespan="off", access_log=False, log_level="warning"
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
        async def open_socket(path="/ws"):
            cookies = "; ".join(
                f"{name}={value}" for name, value in unauth_client.cookies.items()
            )
            headers = {"Cookie": cookies} if cookies else None
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
