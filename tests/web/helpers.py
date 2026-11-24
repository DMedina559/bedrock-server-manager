from bedrock_server_manager.web.main import create_server
from bedrock_server_manager.web.runtime import WebRunOptions, WebRuntime


def attach_runtime(app_context, test_app):
    runtime = WebRuntime()
    server = create_server(app_context, WebRunOptions(), runtime)
    test_app.state.web_runtime = runtime
    runtime.ready()
    return runtime, server


async def issue_token(client, payload):
    response = await client.post("/api/account/tokens", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def login(
    client, username="testuser", password="testpassword", *, headers=None, **data
):
    return await client.post(
        "/auth/token",
        data={"username": username, "password": password, **data},
        headers=headers,
    )
