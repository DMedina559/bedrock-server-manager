import json
import os
import platform
import sys
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

pytest_plugins = ["bsm_test_utils.fixtures"]

from bedrock_server_manager.context import AppContext  # noqa: E402
from bedrock_server_manager.db.database import Database  # noqa: E402
from bedrock_server_manager.db.models import User as UserModel  # noqa: E402
from bedrock_server_manager.db.storage import Storage  # noqa: E402
from bedrock_server_manager.state.app_state import AppState  # noqa: E402
from bedrock_server_manager.utils.auth import (  # noqa: E402
    create_access_token,
    get_password_hash,
)
from bedrock_server_manager.utils.general import startup_checks  # noqa: E402
from bedrock_server_manager.web.app import create_web_app  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_bcm_config(monkeypatch, tmp_path):
    """
    This fixture creates a temporary data and config directory and uses
    bcm_config setter methods to ensure all configuration and data files
    are isolated to the temporary location for the duration of the test.
    """
    test_data_dir = tmp_path / "test_data"
    test_data_dir.mkdir()

    test_config_dir = tmp_path / "test_config"
    test_config_dir.mkdir()

    from bedrock_server_manager.config import bcm_config

    bcm_config.set_custom_config_dir(str(test_config_dir))
    bcm_config.set_custom_data_dir(str(test_data_dir))

    db_path = test_data_dir / "test.db"
    config_file = test_config_dir / "bedrock_server_manager.json"
    config_data = {
        "data_dir": str(test_data_dir),
        "db_url": f"sqlite:///{db_path}",
        "log_level": "DEBUG",
    }

    with open(config_file, "w") as f:
        json.dump(config_data, f)

    yield test_config_dir

    bcm_config.set_custom_config_dir(None)
    bcm_config.set_custom_data_dir(None)
    bcm_config.set_custom_db_url(None)
    bcm_config.set_custom_log_level(None)


@pytest_asyncio.fixture
async def db(isolated_bcm_config, tmp_path, monkeypatch):
    """Provides a fresh Database instance initialized with an isolated async SQLite DB."""
    db_path = tmp_path / "test_data" / "test.db"

    monkeypatch.setattr("bedrock_server_manager.cli.database.files", MagicMock())

    database = Database(f"sqlite+aiosqlite:///{db_path}")
    database.initialize()

    from bedrock_server_manager.db.models import Base

    assert database.engine is not None
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield database

    await database.shutdown()


@pytest_asyncio.fixture
async def storage(db, isolated_bcm_config):
    """Provides a fresh Storage instance."""
    test_data_dir = isolated_bcm_config / "test_data"
    return Storage(db=db, data_dir=str(test_data_dir))


@pytest_asyncio.fixture
async def state(storage):
    """Provides a fresh AppState instance loaded via Storage."""
    app_state = AppState()
    await storage.load_state(app_state)
    return app_state


@pytest_asyncio.fixture
async def app_context(db, storage, state, isolated_bcm_config, tmp_path):
    """Provides a real AppContext instance natively configured with AppState and Storage."""
    context = AppContext()
    context._db = db
    context._storage = storage
    context._state = state
    await context.load()

    startup_checks(context)

    # Create dummy plugin dir so plugin manager can load
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir(exist_ok=True)
    await context.settings.set("paths.plugins", str(plugins_dir))

    context.plugin_manager.plugin_dirs = [plugins_dir]
    await context.plugin_manager.load_plugins()

    yield context

    # --- TEARDOWN ---
    if context._db:
        await context._db.shutdown()


@pytest.fixture
def real_bedrock_server(app_context, tmp_path, dummy_server_zip):
    """Fixture to create a real dummy Bedrock Server instance using bsm-test-utils."""
    import zipfile

    server_name = "test_server"

    server_dir = os.path.join(app_context.settings.get("paths.servers"), server_name)
    os.makedirs(server_dir, exist_ok=True)

    server_config_dir = os.path.join(app_context.settings.config_dir, server_name)
    os.makedirs(server_config_dir, exist_ok=True)

    # Use the dummy_server_zip fixture to generate a fake binary that functions like the real one
    zip_path = dummy_server_zip(target_dir=tmp_path)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(server_dir)

    executable_name = "bedrock_server"
    if platform.system() == "Windows":
        executable_name += ".exe"
    executable_path = os.path.join(server_dir, executable_name)
    os.chmod(executable_path, 0o755)

    server = app_context.get_server(server_name)
    return server


@pytest_asyncio.fixture
async def db_session(db):
    """Fixture to get an async database session directly."""
    async with db.session_manager() as session:
        yield session


@pytest.fixture
def test_app(app_context):
    """Provides a FastAPI application instance for testing."""
    app = create_web_app(app_context)
    return app


@pytest_asyncio.fixture
async def test_admin_user(db_session):
    """Creates a test admin user in the database."""
    user = UserModel(
        username="adminuser",
        hashed_password=get_password_hash("adminpassword"),
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def test_user(db_session, test_admin_user):
    """Creates a test user in the database, also ensuring an admin user exists."""
    user = UserModel(
        username="testuser",
        hashed_password=get_password_hash("testpassword"),
        role="user",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def unauth_client(test_app):
    """Provides an unauthenticated TestClient instance."""
    with TestClient(test_app) as client:
        yield client


@pytest_asyncio.fixture
async def settings(app_context):
    """Provides a fresh Settings instance bound to AppContext."""
    return app_context.settings


@pytest_asyncio.fixture
async def auth_client(test_app, app_context, test_user):
    """Provides an authenticated TestClient instance with a valid token cookie."""
    token = await create_access_token(app_context, {"sub": test_user.username})
    with TestClient(test_app) as client:
        client.cookies.set("access_token_cookie", token)
        yield client


@pytest_asyncio.fixture
async def admin_auth_client(test_app, app_context, test_admin_user):
    """Provides an authenticated TestClient instance for an admin user."""
    token = await create_access_token(app_context, {"sub": test_admin_user.username})
    with TestClient(test_app) as client:
        client.cookies.set("access_token_cookie", token)
        yield client
