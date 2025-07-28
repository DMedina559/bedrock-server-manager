import pytest
import os
from fastapi.testclient import TestClient
from bedrock_server_manager.web.main import app
from bedrock_server_manager.web.dependencies import validate_server_exists
from bedrock_server_manager.web.auth_utils import create_access_token, pwd_context
from datetime import timedelta

TEST_USER = "testuser"
TEST_PASSWORD = "testpassword"


from bedrock_server_manager.web.dependencies import needs_setup


@pytest.fixture(autouse=True)
def mock_dependencies(monkeypatch):
    """Mock dependencies for tests."""

    async def mock_needs_setup():
        return False

    monkeypatch.setattr("bedrock_server_manager.web.main.needs_setup", mock_needs_setup)
    app.dependency_overrides[validate_server_exists] = lambda: "test-server"
    yield
    app.dependency_overrides = {}


from bedrock_server_manager.db.database import SessionLocal, Base, engine
from bedrock_server_manager.db.models import User as UserModel


@pytest.fixture
def client():
    """Create a test client for the app, with authentication and mocked dependencies."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    user = UserModel(
        username=TEST_USER,
        hashed_password=pwd_context.hash(TEST_PASSWORD),
        role="admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()

    os.environ["BEDROCK_SERVER_MANAGER_USERNAME"] = TEST_USER
    os.environ["BEDROCK_SERVER_MANAGER_PASSWORD"] = pwd_context.hash(TEST_PASSWORD)
    os.environ["BEDROCK_SERVER_MANAGER_SECRET_KEY"] = "test-secret-key"

    access_token = create_access_token(
        data={"sub": TEST_USER}, expires_delta=timedelta(minutes=15)
    )
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {access_token}"

    yield client

    del os.environ["BEDROCK_SERVER_MANAGER_USERNAME"]
    del os.environ["BEDROCK_SERVER_MANAGER_PASSWORD"]
    del os.environ["BEDROCK_SERVER_MANAGER_SECRET_KEY"]
    Base.metadata.drop_all(bind=engine)
