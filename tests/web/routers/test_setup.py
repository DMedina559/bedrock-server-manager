"""Integration tests for the setup router endpoints."""

from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import delete

from bedrock_server_manager.db.models import User
from bedrock_server_manager.error import StorageError


async def test_setup_status_and_create_first_user(
    unauth_client: AsyncClient, test_user, app_context
):
    """Test setup status and first-user creation when users exist vs when DB is empty."""
    # Users exist (from test_user fixture)
    status_resp = await unauth_client.get("/api/setup/status")
    assert status_resp.status_code == 200 and status_resp.json()["needs_setup"] is False

    exists_resp = await unauth_client.post(
        "/api/setup/create-first-user",
        json={"username": "admin2", "password": "secure setup passphrase"},
    )
    assert exists_resp.status_code == 400
    assert (
        exists_resp.json()["error"]["message"] == "Application has already been set up."
    )

    # Clear DB and verify needs_setup + first user creation
    async with app_context.db.session_manager() as db:
        await db.execute(delete(User))
        await db.commit()
    app_context._needs_setup = None

    empty_resp = await unauth_client.get("/api/setup/status")
    assert empty_resp.status_code == 200 and empty_resp.json()["needs_setup"] is True

    create_resp = await unauth_client.post(
        "/api/setup/create-first-user",
        json={"username": "admin", "password": "secure setup passphrase"},
    )
    assert create_resp.status_code == 200
    data = create_resp.json()
    assert data["status"] == "success" and "access_token" in data
    assert "access_token_cookie" not in create_resp.cookies


def test_setup_operations_are_in_openapi(test_app):
    schema = test_app.openapi()
    assert (
        schema["paths"]["/api/setup/status"]["get"]["operationId"] == "get_setup_status"
    )
    create = schema["paths"]["/api/setup/create-first-user"]["post"]
    assert create["operationId"] == "create_first_user"
    assert create["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/TokenResponse"
    }
    fields = schema["components"]["schemas"]["TokenResponse"]["properties"]
    assert {"access_token", "token_type", "status", "message"} <= fields.keys()


async def test_setup_storage_outage_returns_unavailable(
    running_app, app_context, monkeypatch
):
    def unavailable(*args, **kwargs):
        raise StorageError("private database diagnostic")

    app_context._needs_setup = None
    async with AsyncClient(
        transport=ASGITransport(app=running_app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        with monkeypatch.context() as fault:
            fault.setattr(type(app_context.db.engine), "connect", unavailable)
            response = await client.get("/api/setup/status")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "unavailable"
    assert "private database diagnostic" not in response.text
    assert app_context._needs_setup is None
