"""Integration tests for the auth router endpoints."""

from httpx2 import ASGITransport, AsyncClient

from bedrock_server_manager.context import AppContext
from bedrock_server_manager.db.models import User as UserModel
from bedrock_server_manager.error import StorageError
from bedrock_server_manager.web.auth import create_access_token


async def test_api_login_flows_and_cookies(
    unauth_client: AsyncClient, test_user: UserModel, app_context: AppContext
):
    """Test login success, remember_me, failures, and cookie Secure flag handling."""
    # Standard bearer login
    response = await unauth_client.post(
        "/auth/token", data={"username": "testuser", "password": "testpassword"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data and data["token_type"] == "bearer"
    assert "access_token_cookie" not in response.cookies

    # Remember me login
    rem_resp = await unauth_client.post(
        "/auth/token",
        data={
            "username": "testuser",
            "password": "testpassword",
            "remember_me": "true",
        },
    )
    assert rem_resp.status_code == 200
    assert "access_token_cookie" not in rem_resp.cookies

    # Wrong password
    bad_resp = await unauth_client.post(
        "/auth/token", data={"username": "testuser", "password": "wrongpassword"}
    )
    assert bad_resp.status_code == 401
    assert "Incorrect username or password" in bad_resp.json()["error"]["message"]

    # Missing username
    missing_resp = await unauth_client.post(
        "/auth/token", data={"password": "testpassword"}
    )
    assert missing_resp.status_code == 422

    # Cookie login with https (Secure) and http (insecure)
    sec_resp = await unauth_client.post(
        "/auth/token",
        data={"username": "testuser", "password": "testpassword"},
        headers={"X-Forwarded-Proto": "https", "X-BSM-Auth-Mode": "cookie"},
    )
    assert sec_resp.status_code == 200
    assert "Secure" in sec_resp.headers.get("set-cookie", "")

    unauth_client.cookies.clear()
    insec_resp = await unauth_client.post(
        "/auth/token",
        data={"username": "testuser", "password": "testpassword"},
        headers={"X-BSM-Auth-Mode": "cookie"},
    )
    assert insec_resp.status_code == 200
    assert "Secure" not in insec_resp.headers.get("set-cookie", "")


async def test_reauth_and_logout_flows(
    auth_client: AsyncClient, unauth_client: AsyncClient, test_admin_user
):
    """Test reauth, remember_me reauth, logout, and unauthorized access."""
    assert (await unauth_client.get("/auth/logout")).status_code == 401
    unauth_reauth = await unauth_client.post("/auth/reauth")
    assert unauth_reauth.status_code == 401
    assert "Not authenticated" in unauth_reauth.json()["error"]["message"]

    old_cookie = auth_client.cookies.get("access_token_cookie")
    response = await auth_client.post("/auth/reauth")
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data and data["token_type"] == "bearer"
    assert data["message"] == "Successfully refreshed token."
    new_cookie = response.cookies.get("access_token_cookie")
    assert new_cookie is not None and old_cookie != new_cookie

    rem_reauth = await auth_client.post("/auth/reauth", data={"remember_me": "true"})
    assert rem_reauth.status_code == 200
    assert "access_token" in rem_reauth.json()
    assert "access_token_cookie" in rem_reauth.cookies

    logout_resp = await auth_client.get("/auth/logout")
    assert logout_resp.status_code == 200
    assert logout_resp.json()["status"] == "success"
    set_cookie_header = logout_resp.headers.get("set-cookie", "")
    assert "access_token_cookie=" in set_cookie_header
    assert "Max-Age=0" in set_cookie_header or "expires=" in set_cookie_header.lower()


async def test_account_authentication_storage_outage_is_not_invalid_token(
    running_app, app_context, monkeypatch, test_user
):
    token = await create_access_token(app_context, {"sub": test_user.username})

    def unavailable():
        raise StorageError("private database diagnostic")

    async with AsyncClient(
        transport=ASGITransport(app=running_app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        with monkeypatch.context() as fault:
            fault.setattr(app_context.storage, "transaction", unavailable)
            response = await client.get(
                "/api/account", headers={"Authorization": f"Bearer {token}"}
            )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "unavailable"
    assert "private database diagnostic" not in response.text
