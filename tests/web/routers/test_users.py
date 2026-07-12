"""
Integration tests for the users router endpoints.
"""

from fastapi.testclient import TestClient

from bedrock_server_manager.db.models import User


def test_list_users_unauthorized(unauth_client: TestClient):
    response = unauth_client.get("/api/users/list")
    assert response.status_code == 401


def test_list_users_forbidden(auth_client: TestClient):
    response = auth_client.get("/api/users/list")
    assert response.status_code == 403


def test_list_users_success(admin_auth_client: TestClient):
    response = admin_auth_client.get("/api/users/list")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(u["role"] == "admin" for u in data)


def test_delete_user_success(admin_auth_client: TestClient, app_context):
    with app_context.db.session_manager() as db:
        user = User(username="to_delete", hashed_password="pw", role="user")
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id

    response = admin_auth_client.post(f"/api/users/{user_id}/delete")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    with app_context.db.session_manager() as db:
        user = db.query(User).filter(User.id == user_id).first()
        assert user is None


def test_delete_user_last_admin(admin_auth_client: TestClient, app_context):
    with app_context.db.session_manager() as db:
        admin = (
            db.query(User)
            .filter(User.role == "admin", User.is_active.is_(True))
            .first()
        )
        admin_id = admin.id

    response = admin_auth_client.post(f"/api/users/{admin_id}/delete")
    assert response.status_code == 400
    assert "Cannot delete the last active admin" in response.json()["detail"]


def test_delete_user_not_found(admin_auth_client: TestClient):
    response = admin_auth_client.post("/api/users/9999/delete")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_disable_user_success(admin_auth_client: TestClient, app_context):
    with app_context.db.session_manager() as db:
        user = User(
            username="to_disable", hashed_password="pw", role="user", is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id

    response = admin_auth_client.post(f"/api/users/{user_id}/disable")
    assert response.status_code == 200

    with app_context.db.session_manager() as db:
        user = db.query(User).filter(User.id == user_id).first()
        assert user.is_active is False


def test_disable_user_last_admin(admin_auth_client: TestClient, app_context):
    with app_context.db.session_manager() as db:
        admin = (
            db.query(User)
            .filter(User.role == "admin", User.is_active.is_(True))
            .first()
        )
        admin_id = admin.id

    response = admin_auth_client.post(f"/api/users/{admin_id}/disable")
    assert response.status_code == 400
    assert "Cannot disable the last active admin" in response.json()["detail"]


def test_enable_user_success(admin_auth_client: TestClient, app_context):
    with app_context.db.session_manager() as db:
        user = User(
            username="to_enable", hashed_password="pw", role="user", is_active=False
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id

    response = admin_auth_client.post(f"/api/users/{user_id}/enable")
    assert response.status_code == 200

    with app_context.db.session_manager() as db:
        user = db.query(User).filter(User.id == user_id).first()
        assert user.is_active is True


def test_update_user_role_success(admin_auth_client: TestClient, app_context):
    with app_context.db.session_manager() as db:
        user = User(username="to_update", hashed_password="pw", role="user")
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id

    response = admin_auth_client.post(
        f"/api/users/{user_id}/role", json={"role": "moderator"}
    )
    assert response.status_code == 200

    with app_context.db.session_manager() as db:
        user = db.query(User).filter(User.id == user_id).first()
        assert user.role == "moderator"


def test_update_user_role_last_admin(admin_auth_client: TestClient, app_context):
    with app_context.db.session_manager() as db:
        admin = (
            db.query(User)
            .filter(User.role == "admin", User.is_active.is_(True))
            .first()
        )
        admin_id = admin.id

    response = admin_auth_client.post(
        f"/api/users/{admin_id}/role", json={"role": "user"}
    )
    assert response.status_code == 400
    assert (
        "Cannot change the role of the last active admin" in response.json()["detail"]
    )
