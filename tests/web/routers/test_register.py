"""
Integration tests for the register router endpoints.
"""

from fastapi.testclient import TestClient
from sqlalchemy import select

from bedrock_server_manager.db.models import RegistrationToken, User


async def test_generate_token_unauthorized(unauth_client: TestClient):
    response = unauth_client.post("/api/register/generate-token", json={"role": "user"})
    assert response.status_code == 401


async def test_generate_token_forbidden(auth_client: TestClient):
    response = auth_client.post("/api/register/generate-token", json={"role": "user"})
    assert response.status_code == 403


async def test_generate_token_success(admin_auth_client: TestClient, app_context):
    response = admin_auth_client.post(
        "/api/register/generate-token", json={"role": "user"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "registration_url" in data

    # Verify token was created in DB
    async with app_context.db.session_manager() as db:
        res = await db.execute(
            select(RegistrationToken).filter(RegistrationToken.role == "user")
        )
        token = res.scalars().first()
        assert token is not None


async def test_validate_token_success(unauth_client: TestClient, app_context):
    # Add token to db
    import time

    token_str = "valid_token_123"
    async with app_context.db.session_manager() as db:
        token = RegistrationToken(
            token=token_str, role="user", expires=int(time.time()) + 3600
        )
        db.add(token)
        await db.commit()

    response = unauth_client.get(f"/api/register/validate/{token_str}")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


async def test_validate_token_not_found(unauth_client: TestClient):
    response = unauth_client.get("/api/register/validate/invalid_token")
    assert response.status_code == 404
    assert response.json()["status"] == "error"


async def test_validate_token_expired(unauth_client: TestClient, app_context):
    import time

    token_str = "expired_token_123"
    async with app_context.db.session_manager() as db:
        token = RegistrationToken(
            token=token_str, role="user", expires=int(time.time()) - 3600
        )
        db.add(token)
        await db.commit()

    response = unauth_client.get(f"/api/register/validate/{token_str}")
    assert response.status_code == 404
    assert response.json()["status"] == "error"


async def test_register_user_success(unauth_client: TestClient, app_context):
    import time

    token_str = "register_token_123"
    async with app_context.db.session_manager() as db:
        token = RegistrationToken(
            token=token_str, role="user", expires=int(time.time()) + 3600
        )
        db.add(token)
        await db.commit()

    response = unauth_client.post(
        f"/api/register/{token_str}",
        json={"username": "new_user", "password": "new_password"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Verify token is deleted and user is created
    async with app_context.db.session_manager() as db:
        res = await db.execute(
            select(RegistrationToken).filter(RegistrationToken.token == token_str)
        )
        token = res.scalars().first()
        assert token is None

        res_user = await db.execute(select(User).filter(User.username == "new_user"))
        user = res_user.scalars().first()
        assert user is not None
        assert user.role == "user"


async def test_register_user_invalid_token(unauth_client: TestClient):
    response = unauth_client.post(
        "/api/register/bad_token",
        json={"username": "new_user", "password": "new_password"},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["status"] == "error"


async def test_register_user_duplicate_username(
    unauth_client: TestClient, app_context, test_user
):
    import time

    token_str = "duplicate_token_123"
    async with app_context.db.session_manager() as db:
        token = RegistrationToken(
            token=token_str, role="user", expires=int(time.time()) + 3600
        )
        db.add(token)
        await db.commit()

    response = unauth_client.post(
        f"/api/register/{token_str}",
        json={"username": test_user.username, "password": "new_password"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["status"] == "error"
    assert "already exists" in response.json()["detail"]["message"]
