"""
Integration tests for the setup router endpoints.
"""

from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import delete

from bedrock_server_manager.db.models import User


async def test_get_setup_status_needs_setup(unauth_client: AsyncClient, app_context):
    """Test setup status when DB is empty."""
    # Ensure DB is empty
    async with app_context.db.session_manager() as db:
        await db.execute(delete(User))
        await db.commit()

    response = await unauth_client.get("/api/setup/status")
    assert response.status_code == 200
    assert response.json()["needs_setup"] is True


async def test_get_setup_status_no_setup_needed(unauth_client: AsyncClient, test_user):
    """Test setup status when DB has users."""
    response = await unauth_client.get("/api/setup/status")
    assert response.status_code == 200
    assert response.json()["needs_setup"] is False


async def test_create_first_user_success(unauth_client: AsyncClient, app_context):
    """Test creating the first user successfully."""
    # Ensure DB is empty
    async with app_context.db.session_manager() as db:
        await db.execute(delete(User))
        await db.commit()

    response = await unauth_client.post(
        "/api/setup/create-first-user",
        json={"username": "admin", "password": "securepassword"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "access_token" in data
    assert "access_token_cookie" in response.cookies


async def test_create_first_user_already_exists(
    unauth_client: AsyncClient, test_user, app_context
):
    """Test creating a user when one already exists."""
    # Ensure needs_setup is evaluated to False
    assert await app_context.check_setup() is False

    response = await unauth_client.post(
        "/api/setup/create-first-user",
        json={"username": "admin2", "password": "securepassword"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["message"] == "Application has already been set up."


def test_setup_operations_are_in_openapi(test_app):
    schema = test_app.openapi()
    assert (
        schema["paths"]["/api/setup/status"]["get"]["operationId"] == "get_setup_status"
    )
    create = schema["paths"]["/api/setup/create-first-user"]["post"]
    assert create["operationId"] == "create_first_user"
    assert create["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/SetupAccountResponse"
    }
    fields = schema["components"]["schemas"]["SetupAccountResponse"]["properties"]
    assert {"access_token", "token_type", "status", "message"} <= fields.keys()


async def test_setup_storage_outage_returns_unavailable(
    running_app, app_context, monkeypatch
):
    from bedrock_server_manager.error import StorageError

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
