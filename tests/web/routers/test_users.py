"""Integration tests for the users router endpoints."""

from httpx2 import AsyncClient
from sqlalchemy import select

from bedrock_server_manager.db.models import User


async def test_users_router_crud_and_last_admin_guards(
    unauth_client: AsyncClient,
    auth_client: AsyncClient,
    admin_auth_client: AsyncClient,
    app_context,
):
    # Authorization checks
    assert (await unauth_client.get("/api/users/list")).status_code == 401
    assert (await auth_client.get("/api/users/list")).status_code == 403

    list_resp = await admin_auth_client.get("/api/users/list")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert len(data) >= 1 and any(u["role"] == "admin" for u in data)

    # Create target user and find admin id
    async with app_context.db.session_manager() as db:
        admin = (
            (
                await db.execute(
                    select(User).filter(User.role == "admin", User.is_active.is_(True))
                )
            )
            .scalars()
            .first()
        )
        admin_id = admin.id

        user = User(
            username="managed_user", hashed_password="pw", role="user", is_active=True
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        user_id = user.id

    # Last admin guards (delete, disable, role change)
    del_admin = await admin_auth_client.post(f"/api/users/{admin_id}/delete")
    assert del_admin.status_code == 400
    assert "Cannot delete the last active admin" in del_admin.json()["error"]["message"]

    dis_admin = await admin_auth_client.post(f"/api/users/{admin_id}/disable")
    assert dis_admin.status_code == 400
    assert (
        "Cannot disable the last active admin" in dis_admin.json()["error"]["message"]
    )

    role_admin = await admin_auth_client.post(
        f"/api/users/{admin_id}/role", json={"role": "user"}
    )
    assert role_admin.status_code == 400
    assert (
        "Cannot change the role of the last active admin"
        in role_admin.json()["error"]["message"]
    )

    # Disable, enable, update role, and delete user
    assert (
        await admin_auth_client.post(f"/api/users/{user_id}/disable")
    ).status_code == 200
    async with app_context.db.session_manager() as db:
        assert (await db.get(User, user_id)).is_active is False

    assert (
        await admin_auth_client.post(f"/api/users/{user_id}/enable")
    ).status_code == 200
    async with app_context.db.session_manager() as db:
        assert (await db.get(User, user_id)).is_active is True

    assert (
        await admin_auth_client.post(
            f"/api/users/{user_id}/role", json={"role": "moderator"}
        )
    ).status_code == 200
    async with app_context.db.session_manager() as db:
        assert (await db.get(User, user_id)).role == "moderator"

    del_resp = await admin_auth_client.post(f"/api/users/{user_id}/delete")
    assert del_resp.status_code == 200 and del_resp.json()["status"] == "success"
    async with app_context.db.session_manager() as db:
        assert await db.get(User, user_id) is None

    # Delete non-existent user
    not_found = await admin_auth_client.post("/api/users/9999/delete")
    assert not_found.status_code == 404
    assert "not found" in not_found.json()["error"]["message"].lower()
