import pytest
import tempfile
import shutil
import os
import sys
from unittest.mock import MagicMock
from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.core.manager import BedrockServerManager
from fastapi.testclient import TestClient
from bedrock_server_manager.web.dependencies import validate_server_exists
from bedrock_server_manager.web.auth_utils import (
    create_access_token,
    get_current_user_optional,
    get_password_hash,
)
from datetime import timedelta
from bedrock_server_manager.db.models import User as UserModel
from bedrock_server_manager.web.app import create_web_app

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))


from appdirs import user_config_dir


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
    """
    This fixture creates a temporary data and config directory and mocks
    appdirs.user_config_dir to ensure all configuration and data files
    are isolated to the temporary location for the duration of the test.
    """
    # Create a temporary directory for the app's data
    test_data_dir = tmp_path / "test_data"
    test_data_dir.mkdir()

    # Create a temporary directory for the app's config files
    test_config_dir = tmp_path / "test_config"
    test_config_dir.mkdir()

    # Mock the user_config_dir function to return our temporary config directory
    monkeypatch.setattr(
        "appdirs.user_config_dir", lambda *args, **kwargs: str(test_config_dir)
    )

    # We also need to set the `data_dir` in the mocked config file
    # for the `Settings` class to find it.
    config_file = test_config_dir / "bedrock_server_manager.json"
    config_data = {"data_dir": str(test_data_dir)}
    with open(config_file, "w") as f:
        import json

        json.dump(config_data, f)

    # The `Settings` class also checks the BSM_DATA_DIR environment variable
    # as a fallback. It's a good practice to mock this as well to be explicit
    # about test isolation, even though the primary path is now mocked.
    monkeypatch.setenv("BSM_DATA_DIR", str(test_data_dir))

    # Reload the bcm_config module to ensure the new mocked paths are used
    import bedrock_server_manager.config.bcm_config as bcm_config
    import importlib

    importlib.reload(bcm_config)

    yield

    # Teardown: Remove the mocked environment variable
    monkeypatch.delenv("BSM_DATA_DIR")
    # Reset the bcm_config module to its original state
    importlib.reload(bcm_config)


@pytest.fixture
def mock_settings(mocker):
    """Fixture for a mocked Settings object."""
    settings = MagicMock()
    settings.get.return_value = "/tmp"
    settings.config_dir = "/tmp/config"
    return settings


@pytest.fixture
def mock_bedrock_server(tmp_path):
    """Fixture for a mocked BedrockServer."""
    # Create a mock object with the same interface as BedrockServer
    server = MagicMock(spec=BedrockServer)

    # Set default attributes for the mock
    server.server_name = "test_server"
    server.server_dir = str(tmp_path / "test_server")
    server.server_config_dir = str(tmp_path / "test_server_config")
    server.is_running.return_value = False
    server.get_status.return_value = "STOPPED"
    server.get_version.return_value = "1.20.0"

    return server


@pytest.fixture
def mock_bedrock_server_manager(mocker):
    """Fixture for a mocked BedrockServerManager."""
    # Create a mock object with the same interface as BedrockServerManager
    manager = MagicMock(spec=BedrockServerManager)

    # Set default attributes for the mock
    manager._app_name_title = "Bedrock Server Manager"
    manager.get_app_version.return_value = "1.0.0"
    manager.get_os_type.return_value = "Linux"
    manager._base_dir = "/servers"
    manager._content_dir = "/content"
    manager._config_dir = "/config"
    manager.list_available_worlds.return_value = ["/content/worlds/world1.mcworld"]
    manager.list_available_addons.return_value = ["/content/addons/addon1.mcpack"]
    manager.get_servers_data.return_value = ([], [])
    manager.can_manage_services = True

    return manager


@pytest.fixture
def temp_file(tmp_path):
    """Creates a temporary file for tests."""
    file = tmp_path / "temp_file"
    file.touch()
    return str(file)


@pytest.fixture
def temp_dir(tmp_path):
    """Creates a temporary directory for tests."""
    return str(tmp_path)


@pytest.fixture
def mock_db_session_manager(mocker):
    def _mock_db_session_manager(db_session):
        mock_session_manager = mocker.MagicMock()
        mock_session_manager.return_value.__enter__.return_value = db_session
        return mock_session_manager

    return _mock_db_session_manager


@pytest.fixture
def db_session(app_context):
    """
    Fixture to get a database session from the app_context.
    """
    with app_context.db.session_manager() as session:
        yield session


@pytest.fixture
def real_bedrock_server(app_context):
    """Fixture for a real BedrockServer instance."""
    server = app_context.get_server("test_server")
    return server


@pytest.fixture
def real_manager(app_context):
    """Fixture for a real BedrockServerManager instance."""
    return app_context.manager


@pytest.fixture(autouse=True)
def app_context(isolated_settings, tmp_path, monkeypatch):
    """Fixture for a real AppContext instance."""
    from bedrock_server_manager.context import AppContext
    from bedrock_server_manager.config.settings import Settings
    from bedrock_server_manager.core.manager import BedrockServerManager
    from bedrock_server_manager.plugins.plugin_manager import PluginManager
    from bedrock_server_manager.db.database import Database
    import os
    import platform

    # Setup: initialize the database with a test-specific URL
    db_path = tmp_path / "test.db"
    db = Database(f"sqlite:///{db_path}")
    db.initialize()

    # Create dummy plugin
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    plugin1_dir = plugins_dir / "plugin1"
    plugin1_dir.mkdir()
    with open(plugin1_dir / "__init__.py", "w") as f:
        f.write(
            "from bedrock_server_manager.plugins.plugin_base import PluginBase\n"
            "class Plugin(PluginBase):\n"
            '    version = "1.0"\n'
            "    def on_load(self):\n"
            "        pass\n"
        )

    settings = Settings(db=db)
    settings.load()
    settings.set("paths.plugins", str(plugins_dir))

    manager = BedrockServerManager(settings)
    manager.load()

    # Create dummy server files
    server_name = "test_server"
    server_dir = os.path.join(settings.get("paths.servers"), server_name)
    os.makedirs(server_dir, exist_ok=True)

    server_config_dir = os.path.join(settings.config_dir, server_name)
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

    context = AppContext(settings=settings, manager=manager, db=db)
    context.load()

    # Load plugins
    context.plugin_manager.plugin_dirs = [plugins_dir]
    context.plugin_manager.load_plugins()

    yield context


TEST_USER = "testuser"
TEST_PASSWORD = "testpassword"


@pytest.fixture
def app(app_context, mocker):
    """Create a FastAPI app instance for testing."""
    # Mock the resource monitor to prevent its background task from running during most tests
    mocker.patch("bedrock_server_manager.web.resource_monitor.ResourceMonitor.start")
    _app = create_web_app(app_context)
    return _app


@pytest.fixture
def mock_dependencies(monkeypatch, app):
    """Mock dependencies for tests."""

    def mock_needs_setup(app_context):
        return False

    monkeypatch.setattr(
        "bedrock_server_manager.config.bcm_config.needs_setup", mock_needs_setup
    )
    app.dependency_overrides[validate_server_exists] = lambda: "test-server"
    yield
    app.dependency_overrides = {}


@pytest.fixture
def client(app):
    """Create a test client for the app, with mocked dependencies."""

    def get_db_override():
        with app.state.app_context.db.session_manager() as session:
            yield session

    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_user(db_session):
    user = UserModel(
        username=TEST_USER,
        hashed_password=get_password_hash(TEST_PASSWORD),
        role="admin",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def authenticated_client(client, authenticated_user, app, app_context):
    async def mock_get_current_user():
        return authenticated_user

    app.dependency_overrides[get_current_user_optional] = mock_get_current_user
    access_token = create_access_token(
        app_context,
        data={"sub": authenticated_user.username},
        expires_delta=timedelta(minutes=15),
    )
    client.headers["Authorization"] = f"Bearer {access_token}"
    yield client
    app.dependency_overrides.clear()
