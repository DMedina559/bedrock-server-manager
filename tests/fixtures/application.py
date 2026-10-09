import json

import pytest
import pytest_asyncio
from httpx2 import ASGITransport, AsyncClient

from bedrock_server_manager.config import bcm_config
from bedrock_server_manager.context import AppContext
from bedrock_server_manager.db.database import Database
from bedrock_server_manager.db.models import User as UserModel
from bedrock_server_manager.db.storage import Storage
from bedrock_server_manager.state.app_state import AppState
from bedrock_server_manager.utils.auth import create_access_token, get_password_hash
from bedrock_server_manager.utils.general import startup_checks
from bedrock_server_manager.web.app import create_web_app


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


@pytest_asyncio.fixture
async def db(isolated_bcm_config, tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'test_data' / 'test.db'}")
    database.initialize()
    # Exercise the production migration path before any repository uses the DB.
    async with database.session_manager():
        pass
    try:
        yield database
    finally:
        await database.shutdown()


@pytest_asyncio.fixture
async def storage(db, isolated_bcm_config):
    """Provides a fresh Storage instance bound to the isolated data directory."""
    test_data_dir = bcm_config.load_config().get("data_dir")
    return Storage(db=db, data_dir=str(test_data_dir))


@pytest_asyncio.fixture
async def state(storage):
    """Provides a fresh AppState instance loaded via Storage."""
    app_state = AppState()
    await storage.load_state(app_state)
    return app_state


@pytest_asyncio.fixture
async def app_context(db, isolated_bcm_config, tmp_path):
    """Provides a real AppContext instance natively configured with AppState and Storage."""
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


@pytest_asyncio.fixture
async def real_bedrock_server(app_context, tmp_path, dummy_server_zip):
    """Install the bsm-test-utils binary through the production installation API."""
    from bedrock_server_manager.api.install import install_new_server
    from bedrock_server_manager.api.models import InstallNewServerRequest

    server_name = "test_server"
    archive = dummy_server_zip(target_dir=tmp_path)
    await install_new_server(
        InstallNewServerRequest(
            server_name=server_name,
            target_version="CUSTOM",
            server_zip_path=str(archive),
        ),
        app_context=app_context,
    )
    server = app_context.get_server(server_name)
    await server.set_target_version("LATEST")
    await app_context.bedrock_process_manager.add_server(server)
    try:
        yield server
    finally:
        await server.stop()


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
async def test_admin_user(db_session, password_hashes):
    """Creates a test admin user in the database."""
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
    """Creates a test user in the database, also ensuring an admin user exists."""
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
    """Provides a fresh Settings instance bound to AppContext."""
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
        yield client


@pytest.fixture(scope="session")
def password_hashes():
    return {
        name: get_password_hash(value)
        for name, value in (("admin", "adminpassword"), ("user", "testpassword"))
    }


@pytest_asyncio.fixture
async def populated_server(real_bedrock_server, valid_mcworld_zip):
    world = await real_bedrock_server.get_world_name()
    await real_bedrock_server.extract_mcworld(str(valid_mcworld_zip), world)
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
