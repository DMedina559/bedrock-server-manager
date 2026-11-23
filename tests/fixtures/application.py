import asyncio
import hashlib
import hmac
import json
import os
import shutil
import sqlite3
import zipfile
from contextlib import asynccontextmanager, closing
from functools import partial
from pathlib import Path

import pytest
import pytest_asyncio
from bsm_test_utils import PackSpec, create_mcworld
from httpx2 import ASGITransport, AsyncClient
from jose import jwt

from bedrock_server_manager.config import bcm_config
from bedrock_server_manager.context import AppContext
from bedrock_server_manager.core.system import base
from bedrock_server_manager.db.database import Database
from bedrock_server_manager.db.models import User as UserModel
from bedrock_server_manager.db.storage import Storage
from bedrock_server_manager.state.app_state import AppState
from bedrock_server_manager.utils.general import startup_checks
from bedrock_server_manager.web.app import create_web_app
from bedrock_server_manager.web.auth import (
    create_access_token,
    get_jwt_secret_key,
    get_password_hash,
)

_SERVER_TEMPLATE_VERSION: str = "1.20.0.01"


@pytest.fixture(autouse=True)
def isolated_bcm_config(monkeypatch, tmp_path):
    """Isolate bootstrap configuration while preserving the caller's overrides."""
    for setting in ("config_dir", "data_dir", "db_url", "log_level"):
        monkeypatch.delenv(f"BSM_{setting.upper()}", raising=False)
        monkeypatch.setattr(bcm_config, f"_custom_{setting}", None)

    data_dir = tmp_path / "test_data"
    data_dir.mkdir()
    config_dir = tmp_path / "test_config"
    bcm_config.set_custom_config_dir(str(config_dir))
    bcm_config.set_custom_data_dir(str(data_dir))

    config_path = Path(bcm_config.get_config_path())
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "data_dir": str(data_dir),
                "db_url": f"sqlite:///{data_dir / 'test.db'}",
                "logging_level": "DEBUG",
            }
        ),
        encoding="utf-8",
    )
    return config_dir


@pytest.fixture
def fast_dummy_startup(monkeypatch):
    """Use immediate readiness unless the test requests a startup delay."""
    monkeypatch.setenv(
        "BSM_DUMMY_STARTUP_DELAY_MS", os.environ.get("BSM_DUMMY_STARTUP_DELAY_MS", "0")
    )


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
    return Storage(db=db, data_dir=bcm_config.load_config()["data_dir"])


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
    try:
        await context.load()
        context.loop = asyncio.get_running_loop()
        startup_checks(context)
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir(exist_ok=True)
        await context.settings.set("paths.plugins", str(plugins_dir))
        context.plugin_manager.plugin_dirs = [plugins_dir]
        yield context
    finally:
        await context.shutdown()


@pytest.fixture
def dummy_player_command():
    def command(action: str, name: str, xuid: str) -> str:
        return f"__DUMMY__ {action} {name} xuid={xuid}"

    return command


@pytest_asyncio.fixture
async def real_bedrock_server(app_context, dummy_server_template, fast_dummy_startup):
    """Install an isolated dummy server for process integration tests."""
    server_name = "test_server"
    server = app_context.prepare_server(server_name)
    shutil.copytree(dummy_server_template, server.paths.server_dir, dirs_exist_ok=True)
    os.makedirs(server.paths.server_config_dir, exist_ok=True)
    os.makedirs(server.paths.server_log_dir, exist_ok=True)
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


def _csrf_for_token(token: str, secret: str) -> str:
    sid = jwt.get_unverified_claims(token)["sid"]
    return hmac.new(secret.encode(), f"csrf:{sid}".encode(), hashlib.sha256).hexdigest()


@asynccontextmanager
async def _build_auth_client(running_app, app_context, user):
    token = await create_access_token(app_context, {"sub": user.username})
    secret = await get_jwt_secret_key(app_context.settings)
    async with AsyncClient(
        transport=ASGITransport(app=running_app),
        base_url="http://testserver",
        follow_redirects=True,
        cookies={"access_token_cookie": token},
        headers={"X-CSRF-Token": _csrf_for_token(token, secret)},
    ) as client:
        yield client


@pytest_asyncio.fixture
async def auth_client(running_app, app_context, test_user):
    async with _build_auth_client(running_app, app_context, test_user) as client:
        yield client


@pytest_asyncio.fixture
async def admin_auth_client(running_app, app_context, test_admin_user):
    async with _build_auth_client(running_app, app_context, test_admin_user) as client:
        yield client


@pytest.fixture(scope="session")
def password_hashes():
    return {
        name: get_password_hash(value)
        for name, value in (("admin", "adminpassword"), ("user", "testpassword"))
    }


@pytest.fixture(scope="session")
def world_template(tmp_path_factory):
    root = tmp_path_factory.mktemp("world-template")
    archive = create_mcworld(
        root,
        name="Valid World",
        packs=[
            PackSpec(name="World BP", pack_type="data"),
            PackSpec(name="World RP", pack_type="resources"),
        ],
    )
    destination = root / "world"
    with zipfile.ZipFile(archive) as source:
        source.extractall(destination)
    return destination


@pytest_asyncio.fixture
async def populated_server(real_bedrock_server, world_template):
    world = await real_bedrock_server.get_world_name()
    target_world = Path(real_bedrock_server.paths.server_dir) / "worlds" / world
    shutil.copytree(world_template, target_world, dirs_exist_ok=True)
    return real_bedrock_server


@pytest.fixture
def plugin_factory(app_context):
    async def load(name, source):
        path = app_context.plugin_manager.plugin_dirs[0] / f"{name}.py"
        path.write_text(source)
        await app_context.plugin_service.register_or_update_plugin(name, enabled=True)
        assert await app_context.plugin_manager.load_plugin_by_name(name), name
        return next(
            plugin
            for plugin in app_context.plugin_manager.plugins
            if plugin.api._plugin_name == name
        )

    return load


@pytest.fixture
def wait_for_task():
    async def wait(context, task_id):
        snapshot = None
        try:
            async with asyncio.timeout(20):
                while True:
                    snapshot = await context.task_manager.get_task(task_id)
                    if snapshot.status in {"completed", "failed", "cancelled"}:
                        assert snapshot.status == "completed", snapshot.model_dump()
                        return snapshot
                    await asyncio.sleep(0.01)
        except TimeoutError as error:
            last = snapshot.model_dump() if snapshot is not None else None
            raise AssertionError(
                f"Task {task_id} timed out. Last status: {last}"
            ) from error

    return wait


@pytest_asyncio.fixture
async def download_api(app_context, mock_bedrock_api, fast_dummy_startup, monkeypatch):
    await app_context.settings.set(
        "downloader.download_url", f"{mock_bedrock_api.url}/api/v1.0/download/links"
    )
    monkeypatch.setattr(
        base,
        "check_internet_connectivity",
        partial(base.check_internet_connectivity, url=mock_bedrock_api.url),
    )
    return mock_bedrock_api
