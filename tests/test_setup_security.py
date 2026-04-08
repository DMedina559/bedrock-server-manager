import pytest
from fastapi.testclient import TestClient

from bedrock_server_manager.db.models import User
from bedrock_server_manager.web.app import create_web_app
from bedrock_server_manager.web.auth_utils import get_password_hash


@pytest.fixture
def client(app_context):
    app = create_web_app(app_context)
    return TestClient(app)


def test_setup_status_needs_setup(client, app_context):
    # Ensure no users exist (fixture might seed one, so clear it)
    with app_context.db.session_manager() as db:
        db.query(User).delete()
        db.commit()

    response = client.get("/api/setup/status")
    assert response.status_code == 200
    assert response.json() == {"needs_setup": True}


def test_setup_status_setup_done(client, app_context):
    # Create a user
    with app_context.db.session_manager() as db:
        user = User(
            username="admin",
            hashed_password=get_password_hash("password"),
            role="admin",
        )
        db.add(user)
        db.commit()

    response = client.get("/api/setup/status")
    assert response.status_code == 200
    assert response.json() == {"needs_setup": False}

    # Updated to point to legacy setup route
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/app/"
