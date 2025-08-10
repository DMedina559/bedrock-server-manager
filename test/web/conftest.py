import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Generator
from bedrock_server_manager.db.database import Base, get_db
from bedrock_server_manager.web.dependencies import validate_server_exists, needs_setup
from bedrock_server_manager.web.auth_utils import (
    create_access_token,
    pwd_context,
    get_current_user_optional,
)
from datetime import timedelta
from bedrock_server_manager.db.models import User as UserModel
from unittest.mock import MagicMock
from bedrock_server_manager.app_context import create_web_app

TEST_USER = "testuser"
TEST_PASSWORD = "testpassword"
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def db_engine():
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_db(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    db = TestingSessionLocal(bind=connection)

    yield db

    db.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def app(app_context):
    """Create a FastAPI app instance for testing."""
    # The app_context fixture is defined in the root conftest.py
    # and is available to all tests.
    _app = create_web_app(app_context)
    return _app


@pytest.fixture(autouse=True)
def mock_dependencies(monkeypatch, app):
    """Mock dependencies for tests."""

    async def mock_needs_setup():
        return False

    monkeypatch.setattr(
        "bedrock_server_manager.app_context.needs_setup", mock_needs_setup
    )
    app.dependency_overrides[validate_server_exists] = lambda: "test-server"
    yield
    app.dependency_overrides = {}


@pytest.fixture
def client(app, test_db):
    """Create a test client for the app, with mocked dependencies."""
    app.dependency_overrides[get_db] = lambda: test_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_user(test_db):
    user = UserModel(
        username=TEST_USER,
        hashed_password=pwd_context.hash(TEST_PASSWORD),
        role="admin",
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def authenticated_client(client, authenticated_user, app):
    async def mock_get_current_user():
        return authenticated_user

    app.dependency_overrides[get_current_user_optional] = mock_get_current_user
    access_token = create_access_token(
        data={"sub": authenticated_user.username}, expires_delta=timedelta(minutes=15)
    )
    client.headers["Authorization"] = f"Bearer {access_token}"
    yield client
    app.dependency_overrides.clear()
