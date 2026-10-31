import json
import os
import shutil
import sqlite3
import zipfile
from contextlib import closing
from pathlib import Path

import pytest
import pytest_asyncio
from httpx2 import ASGITransport, AsyncClient

from bedrock_server_manager.config import bcm_config
from bedrock_server_manager.context import AppContext
from bedrock_server_manager.db.database import Database
from bedrock_server_manager.db.models import User as UserModel
from bedrock_server_manager.db.storage import Storage
from bedrock_server_manager.state.app_state import AppState
from bedrock_server_manager.utils.general import startup_checks
from bedrock_server_manager.web.app import create_web_app
from bedrock_server_manager.web.auth import create_access_token, get_password_hash

_SERVER_TEMPLATE_DIR: Path | None = None
_SERVER_TEMPLATE_VERSION: str = "1.20.0.01"
_WORLD_TEMPLATE_DIR: Path | None = None


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


@pytest.fixture(scope="session")
def migrated_database(tmp_path_factory):
    """Migrate an empty SQLite template once; share no engines or live state."""
    path = tmp_path_factory.mktemp("database-schema") / "empty.db"
    database = Database(f"sqlite:///{path}")
    database._run_alembic_upgrade()
    return path


@pytest.fixture(scope="session")
def schema_revision(migrated_database):
    with closing(sqlite3.connect(migrated_database)) as conn:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        return str(row[0]) if row else None


@pytest_asyncio.fixture
async def db(isolated_bcm_config, tmp_path, migrated_database, schema_revision):
    """Give each test its own migrated database, engine and event-loop resources."""
    path = tmp_path / "test_data" / "test.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(migrated_database, path)
    database = Database(f"sqlite+aiosqlite:///{path}")
    database.initialize()
    database.schema_revision = schema_revision
    database._tables_created = True
    try:
        yield database
    finally:
        await database.shutdown()


@pytest_asyncio.fixture
async def storage(db, isolated_bcm_config):
    """Provide a fresh Storage instance bound to the isolated data directory."""
    test_data_dir = bcm_config.load_config().get("data_dir")
    return Storage(db=db, data_dir=str(test_data_dir))


@pytest_asyncio.fixture
async def state(storage):
    """Provide a fresh AppState instance loaded via Storage."""
    app_state = AppState()
    await storage.load_state(app_state)
    return app_state


@pytest_asyncio.fixture
async def app_context(db, isolated_bcm_config, tmp_path):
    """Provide a real AppContext instance natively configured with AppState and Storage."""
    context = AppContext()
    context._db = db
    await context.load()
    import asyncio

    context.loop = asyncio.get_running_loop()

    startup_checks(context)

    # Create dummy plugin dir so plugin manager can load
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir(exist_ok=True)
    await context.settings.set("paths.plugins", str(plugins_dir))

    context.plugin_manager.plugin_dirs = [plugins_dir]
    await context.plugin_manager.load_plugins()

    yield context

    await context.shutdown()


async def _ensure_server_template(tmp_path_factory, dummy_server_zip) -> Path:
    from bedrock_server_manager.core.system.base import set_server_folder_permissions

    global _SERVER_TEMPLATE_DIR
    if _SERVER_TEMPLATE_DIR is None or not _SERVER_TEMPLATE_DIR.exists():
        base = tmp_path_factory.mktemp("server-template")
        archive = dummy_server_zip(target_dir=base, version=_SERVER_TEMPLATE_VERSION)
        template_dir = base / "extracted"
        template_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(template_dir)
        await set_server_folder_permissions(str(template_dir))
        _SERVER_TEMPLATE_DIR = template_dir
    return _SERVER_TEMPLATE_DIR


@pytest_asyncio.fixture
async def real_bedrock_server(app_context, tmp_path_factory, dummy_server_zip):
    """Install the bsm-test-utils binary using a session-cached extracted template."""
    server_name = "test_server"
    template_dir = await _ensure_server_template(tmp_path_factory, dummy_server_zip)
    server = app_context.prepare_server(server_name)
    shutil.copytree(template_dir, server.paths.server_dir, dirs_exist_ok=True)
    os.makedirs(server.paths.server_config_dir, exist_ok=True)
    await app_context.server_service.register_or_update_server(
        server_name,
        installed_version=_SERVER_TEMPLATE_VERSION,
        status="INSTALLED",
        target_version="LATEST",
    )
    await app_context.bedrock_process_manager.add_server(server)
    try:
        yield server
    finally:
        if server.process._process is not None or os.path.exists(
            server.get_pid_file_path()
        ):
            await server.stop()


@pytest_asyncio.fixture
async def db_session(db):
    """Fixture to get an async database session directly."""
    async with db.session_manager() as session:
        yield session


@pytest.fixture
def test_app(app_context):
    """Provide a FastAPI application instance for testing."""
    app = create_web_app(app_context)
    return app


@pytest_asyncio.fixture
async def test_admin_user(db_session, password_hashes):
    """Create a test admin user in the database."""
    user = UserModel(
        username="adminuser",
        hashed_password=password_hashes["admin"],
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def test_user(db_session, test_admin_user, password_hashes):
    """Create a test user in the database, also ensuring an admin user exists."""
    user = UserModel(
        username="testuser",
        hashed_password=password_hashes["user"],
        role="user",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def running_app(test_app):
    async with test_app.router.lifespan_context(test_app):
        yield test_app


@pytest_asyncio.fixture
async def unauth_client(running_app):
    async with AsyncClient(
        transport=ASGITransport(app=running_app),
        base_url="http://testserver",
        follow_redirects=True,
    ) as client:
        yield client


@pytest_asyncio.fixture
async def settings(app_context):
    """Provide a fresh Settings instance bound to AppContext."""
    return app_context.settings


@pytest_asyncio.fixture
async def auth_client(running_app, app_context, test_user):
    token = await create_access_token(app_context, {"sub": test_user.username})
    async with AsyncClient(
        transport=ASGITransport(app=running_app),
        base_url="http://testserver",
        follow_redirects=True,
        cookies={"access_token_cookie": token},
    ) as client:
        account = await client.get("/api/account")
        client.headers["X-CSRF-Token"] = account.headers["X-BSM-CSRF-Token"]
        yield client


@pytest_asyncio.fixture
async def admin_auth_client(running_app, app_context, test_admin_user):
    token = await create_access_token(app_context, {"sub": test_admin_user.username})
    async with AsyncClient(
        transport=ASGITransport(app=running_app),
        base_url="http://testserver",
        follow_redirects=True,
        cookies={"access_token_cookie": token},
    ) as client:
        account = await client.get("/api/account")
        client.headers["X-CSRF-Token"] = account.headers["X-BSM-CSRF-Token"]
        yield client


@pytest.fixture(scope="session")
def password_hashes():
    return {
        name: get_password_hash(value)
        for name, value in (("admin", "adminpassword"), ("user", "testpassword"))
    }


@pytest_asyncio.fixture
async def populated_server(real_bedrock_server, tmp_path_factory, valid_mcworld_zip):
    global _WORLD_TEMPLATE_DIR
    if _WORLD_TEMPLATE_DIR is None or not _WORLD_TEMPLATE_DIR.exists():
        world_template = tmp_path_factory.mktemp("world-template") / "world"
        world_template.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(valid_mcworld_zip, "r") as zf:
            zf.extractall(world_template)
        _WORLD_TEMPLATE_DIR = world_template
    world = await real_bedrock_server.get_world_name()
    target_world = Path(real_bedrock_server.paths.server_dir) / "worlds" / world
    shutil.copytree(_WORLD_TEMPLATE_DIR, target_world, dirs_exist_ok=True)
    return real_bedrock_server


@pytest_asyncio.fixture
async def plugin_factory(app_context, tmp_path):
    async def load(name, source):
        path = tmp_path / "plugins" / f"{name}.py"
        path.write_text(source)
        await app_context.plugin_service.register_or_update_plugin(name, enabled=True)
        assert await app_context.plugin_manager.load_plugin_by_name(name)
        return next(
            plugin
            for plugin in app_context.plugin_manager.plugins
            if plugin.api._plugin_name == name
        )

    return load


@pytest.fixture
def wait_for_task():
    async def wait(context, task_id):
        import asyncio

        async with asyncio.timeout(20):
            while True:
                snapshot = await context.task_manager.get_task(task_id)
                if snapshot.status in {"completed", "failed", "cancelled"}:
                    assert snapshot.status == "completed", snapshot.model_dump()
                    return snapshot
                await asyncio.sleep(0.01)

    return wait


@pytest_asyncio.fixture
async def download_api(app_context, mock_bedrock_api, monkeypatch):
    from functools import partial

    from bedrock_server_manager.core.system import base

    await app_context.settings.set(
        "downloader.download_url", f"{mock_bedrock_api.url}/api/v1.0/download/links"
    )
    monkeypatch.setattr(
        base,
        "check_internet_connectivity",
        partial(base.check_internet_connectivity, url=mock_bedrock_api.url),
    )
    return mock_bedrock_api
