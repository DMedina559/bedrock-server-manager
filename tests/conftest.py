import json
import os
import platform
import sys
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from bedrock_server_manager.config.settings import Settings  # noqa: E402
from bedrock_server_manager.context import AppContext  # noqa: E402
from bedrock_server_manager.db.database import Database  # noqa: E402
from bedrock_server_manager.db.models import User as UserModel  # noqa: E402
from bedrock_server_manager.utils.auth import (  # noqa: E402
    create_access_token,
    get_password_hash,
)
from bedrock_server_manager.web.app import create_web_app  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_bcm_config(monkeypatch, tmp_path):
    """
    This fixture creates a temporary data and config directory and mocks
    platformdirs.user_config_dir to ensure all configuration and data files
    are isolated to the temporary location for the duration of the test.
    """
    test_data_dir = tmp_path / "test_data"
    test_data_dir.mkdir()

    test_config_dir = tmp_path / "test_config"
    test_config_dir.mkdir()

    monkeypatch.setattr(
        "bedrock_server_manager.config.bcm_config.user_config_dir",
        lambda *args, **kwargs: str(test_config_dir),
    )

    db_path = test_data_dir / "test.db"
    config_file = test_config_dir / "bedrock_server_manager.json"
    config_data = {"data_dir": str(test_data_dir), "db_url": f"sqlite:///{db_path}"}

    with open(config_file, "w") as f:
        json.dump(config_data, f)

    monkeypatch.setenv("BSM_DATA_DIR", str(test_data_dir))

    # Reloading inside a fixture is a nightmare because other fixtures import the module
    # and hold a reference to the OLD namespace. Let's try NOT reloading. We already patched it globally.
    # We will just patch the values.

    yield test_config_dir

    monkeypatch.delenv("BSM_DATA_DIR", raising=False)


@pytest.fixture
def db(isolated_bcm_config, tmp_path, monkeypatch):
    """Provides a fresh Database instance initialized with an isolated SQLite DB."""
    # We use a memory database for speed and isolation
    db_path = tmp_path / "test_data" / "test.db"

    # ensure mock for alembic files since they might be missing or not findable in tests sometimes
    monkeypatch.setattr("bedrock_server_manager.cli.database.files", MagicMock())

    database = Database(f"sqlite:///{db_path}")
    database.initialize()

    # Ensure tables are created for tests
    from bedrock_server_manager.db.models import Base

    Base.metadata.create_all(database.engine)

    yield database

    database.close()


@pytest.fixture
def settings(db):
    """Provides a fresh Settings instance."""
    settings_instance = Settings(db=db)
    settings_instance.load()
    return settings_instance


@pytest.fixture
def app_context(settings, db, tmp_path):
    """Provides a real AppContext instance."""
    context = AppContext(settings=settings, db=db)
    context.load()

    # Create dummy plugin dir so plugin manager can load
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir(exist_ok=True)
    settings.set("paths.plugins", str(plugins_dir))

    context.plugin_manager.plugin_dirs = [plugins_dir]
    context.plugin_manager.load_plugins()

    yield context


@pytest.fixture
def real_bedrock_server(app_context, tmp_path):
    """Fixture to create dummy files representing a server for BedrockServer instance testing."""
    server_name = "test_server"

    server_dir = os.path.join(app_context.settings.get("paths.servers"), server_name)
    os.makedirs(server_dir, exist_ok=True)

    server_config_dir = os.path.join(app_context.settings.config_dir, server_name)
    os.makedirs(server_config_dir, exist_ok=True)

    properties_file = os.path.join(server_dir, "server.properties")
    with open(properties_file, "w") as f:
        f.write("server-name=test-server\nmax-players=5\nlevel-name=world\n")

    executable_name = "bedrock_server"
    if platform.system() == "Windows":
        executable_name += ".exe"
    executable_path = os.path.join(server_dir, executable_name)
    with open(executable_path, "w") as f:
        f.write(
            "#!/bin/bash\n"
            "while read line; do\n"
            '  if [[ "$line" == "stop" ]]; then\n'
            "    exit 0\n"
            "  fi\n"
            "done\n"
        )
    os.chmod(executable_path, 0o755)

    server = app_context.get_server(server_name)
    return server


@pytest.fixture
def db_session(db):
    """Fixture to get a database session directly."""
    with db.session_manager() as session:
        yield session


@pytest.fixture
def test_app(app_context):
    """Provides a FastAPI application instance for testing."""
    app = create_web_app(app_context)
    return app


@pytest.fixture
def unauth_client(test_app):
    """Provides an unauthenticated TestClient instance."""
    return TestClient(test_app)


@pytest.fixture
def test_user(db_session):
    """Creates a test user in the database."""
    user = UserModel(
        username="testuser",
        hashed_password=get_password_hash("testpassword"),
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_admin_user(db_session):
    """Creates a test admin user in the database."""
    user = UserModel(
        username="adminuser",
        hashed_password=get_password_hash("adminpassword"),
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def auth_client(test_app, app_context, test_user):
    """Provides an authenticated TestClient instance with a valid token cookie."""
    token = create_access_token(app_context, {"sub": test_user.username})
    client = TestClient(test_app)
    client.cookies.set("access_token_cookie", token)
    return client


@pytest.fixture
def admin_auth_client(test_app, app_context, test_admin_user):
    """Provides an authenticated TestClient instance for an admin user."""
    token = create_access_token(app_context, {"sub": test_admin_user.username})
    client = TestClient(test_app)
    client.cookies.set("access_token_cookie", token)
    return client
