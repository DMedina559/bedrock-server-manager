import pytest
from unittest.mock import patch, MagicMock
import os
import json
import importlib

from bedrock_server_manager.utils.migration import (
    migrate_env_vars_to_config_file,
    migrate_players_json_to_db,
    migrate_env_auth_to_db,
    migrate_server_config_v1_to_v2,
    migrate_settings_v1_to_v2,
    migrate_env_token_to_db,
    migrate_plugin_config_to_db,
    migrate_server_config_to_db,
    migrate_services_to_db,
    migrate_json_settings_to_db,
)
from bedrock_server_manager.db.models import Player, User, Server, Setting
from bedrock_server_manager.error import ConfigurationError


@pytest.fixture
def mock_db_session():
    """Fixture for a mocked database session."""
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = None
    return session


@pytest.fixture
def app_context(tmp_path, mock_db_session):
    """Fixture for a mocked AppContext."""

    class MockSettings:
        def __init__(self):
            self.config_dir = str(tmp_path)
            self._data = {}
            self.reload = MagicMock()

        def get(self, key):
            return self._data.get(key)

        def set(self, key, value):
            self._data[key] = value

    class MockAppContext:
        def __init__(self):
            self.settings = MockSettings()
            self._servers = {}
            self.db = MagicMock()
            self.db.session_manager.return_value.__enter__.return_value = (
                mock_db_session
            )

        def get_server(self, server_name):
            if server_name not in self._servers:
                mock_server = MagicMock()
                mock_server.server_name = server_name
                mock_server.is_installed.return_value = True
                self._servers[server_name] = mock_server
            return self._servers[server_name]

    return MockAppContext()


class TestMigratePlayersJsonToDb:
    def test_migrate_players_json_to_db_success(
        self, tmp_path, mock_db_session, app_context
    ):
        players_data = {
            "players": [
                {"name": "player1", "xuid": "123"},
                {"name": "player2", "xuid": "456"},
            ]
        }
        players_json_path = tmp_path / "players.json"
        backup_json_path = tmp_path / "players.json.bak"
        with open(players_json_path, "w") as f:
            json.dump(players_data, f)

        migrate_players_json_to_db(app_context)

        assert mock_db_session.add.call_count == 2
        mock_db_session.commit.assert_called_once()
        assert backup_json_path.exists()

    def test_migrate_players_json_to_db_file_not_found(self, app_context):
        app_context.settings.config_dir = "non_existent_dir"
        migrate_players_json_to_db(app_context)
        assert app_context.db.session_manager.call_count == 0

    def test_migrate_players_json_to_db_invalid_json(self, tmp_path, app_context):
        players_json_path = tmp_path / "players.json"
        with open(players_json_path, "w") as f:
            f.write("{invalid_json}")

        migrate_players_json_to_db(app_context)
        assert app_context.db.session_manager.call_count == 0

    def test_migrate_players_json_to_db_db_error(
        self, tmp_path, mock_db_session, app_context
    ):
        players_data = {
            "players": [
                {"name": "player1", "xuid": "123"},
                {"name": "player2", "xuid": "456"},
            ]
        }
        players_json_path = tmp_path / "players.json"
        backup_json_path = tmp_path / "players.json.bak"
        with open(players_json_path, "w") as f:
            json.dump(players_data, f)

        mock_db_session.commit.side_effect = Exception("DB error")

        migrate_players_json_to_db(app_context)

        assert mock_db_session.add.call_count == 2
        mock_db_session.rollback.assert_called_once()
        assert not backup_json_path.exists()
        assert players_json_path.exists()
        with open(players_json_path, "r") as f:
            assert json.load(f) == players_data


class TestMigrateEnvAuthToDb:
    @patch.dict(
        os.environ,
        {
            "BEDROCK_SERVER_MANAGER_USERNAME": "testuser",
            "BEDROCK_SERVER_MANAGER_PASSWORD": "testpassword",
        },
        clear=True,
    )
    def test_migrate_env_auth_to_db_success(self, mock_db_session, app_context):
        migrate_env_auth_to_db(app_context)

        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @patch.dict(os.environ, {}, clear=True)
    def test_migrate_env_auth_to_db_no_env_vars(self, app_context):
        migrate_env_auth_to_db(app_context)
        assert app_context.db.session_manager.call_count == 0

    @patch.dict(
        os.environ,
        {
            "BEDROCK_SERVER_MANAGER_USERNAME": "testuser",
            "BEDROCK_SERVER_MANAGER_PASSWORD": "testpassword",
        },
        clear=True,
    )
    def test_migrate_env_auth_to_db_user_exists(self, mock_db_session, app_context):
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = (
            User()
        )

        migrate_env_auth_to_db(app_context)

        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_not_called()

    @patch.dict(
        os.environ,
        {
            "BEDROCK_SERVER_MANAGER_USERNAME": "testuser",
            "BEDROCK_SERVER_MANAGER_PASSWORD": "testpassword",
        },
        clear=True,
    )
    def test_migrate_env_auth_to_db_db_error(self, mock_db_session, app_context):
        mock_db_session.commit.side_effect = Exception("DB error")

        migrate_env_auth_to_db(app_context)

        mock_db_session.add.assert_called_once()
        mock_db_session.rollback.assert_called_once()

    @patch.dict(
        os.environ,
        {
            "BEDROCK_SERVER_MANAGER_USERNAME": "testuser_hashed",
            "BEDROCK_SERVER_MANAGER_PASSWORD": "$2b$12$CoDITwbHQm4rzcWNk6VbR.we8YuV4vf9zUmZ6gQvsIVwcz7BWTOAy",
        },
        clear=True,
    )
    def test_migrate_env_auth_to_db_with_hashed_password(
        self, mock_db_session, app_context
    ):
        migrate_env_auth_to_db(app_context)

        mock_db_session.add.assert_called_once()
        added_user = mock_db_session.add.call_args[0][0]
        assert added_user.username == "testuser_hashed"
        assert (
            added_user.hashed_password
            == "$2b$12$CoDITwbHQm4rzcWNk6VbR.we8YuV4vf9zUmZ6gQvsIVwcz7BWTOAy"
        )
        mock_db_session.commit.assert_called_once()


class TestMigrateServerConfigV1ToV2:
    def test_migrate_server_config_v1_to_v2_success(self):
        old_config = {
            "installed_version": "1.0.0",
            "target_version": "1.1.0",
            "status": "stopped",
            "autoupdate": "true",
            "custom_key": "custom_value",
        }
        default_config = {
            "config_schema_version": 2,
            "server_info": {
                "installed_version": "UNKNOWN",
                "status": "UNKNOWN",
            },
            "settings": {
                "autoupdate": False,
                "autostart": False,
                "target_version": "UNKNOWN",
            },
            "custom": {},
        }

        new_config = migrate_server_config_v1_to_v2(old_config, default_config)

        assert new_config["config_schema_version"] == 2
        assert new_config["server_info"]["installed_version"] == "1.0.0"
        assert new_config["settings"]["target_version"] == "1.1.0"
        assert new_config["server_info"]["status"] == "stopped"
        assert new_config["settings"]["autoupdate"] is True
        assert new_config["custom"]["custom_key"] == "custom_value"

    def test_migrate_server_config_v1_to_v2_empty_config(self):
        old_config = {}
        default_config = {
            "config_schema_version": 2,
            "server_info": {
                "installed_version": "UNKNOWN",
                "status": "UNKNOWN",
            },
            "settings": {
                "autoupdate": False,
                "autostart": False,
                "target_version": "UNKNOWN",
            },
            "custom": {},
        }

        new_config = migrate_server_config_v1_to_v2(old_config, default_config)

        assert new_config == default_config


class TestMigrateSettingsV1ToV2:
    def test_migrate_settings_v1_to_v2_success(self, tmp_path):
        old_config = {
            "BASE_DIR": "/servers",
            "CONTENT_DIR": "/content",
            "DOWNLOAD_DIR": "/downloads",
            "BACKUP_DIR": "/backups",
            "PLUGIN_DIR": "/plugins",
            "LOG_DIR": "/logs",
            "BACKUP_KEEP": 5,
            "DOWNLOAD_KEEP": 5,
            "LOGS_KEEP": 5,
            "FILE_LOG_LEVEL": "INFO",
            "CLI_LOG_LEVEL": "WARNING",
            "WEB_PORT": 8080,
            "TOKEN_EXPIRES_WEEKS": 2,
        }
        default_config = {
            "config_version": 2,
            "paths": {
                "servers": "",
                "content": "",
                "downloads": "",
                "backups": "",
                "plugins": "",
                "logs": "",
                "themes": "",
            },
            "retention": {"backups": 3, "downloads": 3, "logs": 3},
            "logging": {"file_level": "INFO", "cli_level": "WARNING"},
            "web": {"host": "127.0.0.1", "port": 11325, "token_expires_weeks": 4},
            "custom": {},
        }
        config_path = tmp_path / "config.json"
        with open(config_path, "w") as f:
            json.dump(old_config, f)

        new_config = migrate_settings_v1_to_v2(
            old_config, str(config_path), default_config
        )

        assert new_config["paths"]["servers"] == "/servers"
        assert new_config["retention"]["backups"] == 5
        assert new_config["web"]["port"] == 8080

    def test_migrate_settings_v1_to_v2_backup_fails(self, tmp_path):
        old_config = {}
        default_config = {}
        config_path = tmp_path / "config.json"
        with open(config_path, "w") as f:
            json.dump(old_config, f)

        with patch("os.rename", side_effect=OSError("Permission denied")):
            with pytest.raises(ConfigurationError):
                migrate_settings_v1_to_v2(old_config, str(config_path), default_config)


class TestMigrateEnvTokenToDb:
    @patch.dict(os.environ, {"BEDROCK_SERVER_MANAGER_TOKEN": "test_token"}, clear=True)
    def test_migrate_env_token_to_db_success(self, app_context):
        migrate_env_token_to_db(app_context)
        assert app_context.settings.get("web.jwt_secret_key") == "test_token"

    @patch.dict(os.environ, {}, clear=True)
    def test_migrate_env_token_to_db_no_token(self, app_context):
        initial_token = "initial_token"
        app_context.settings.set("web.jwt_secret_key", initial_token)
        migrate_env_token_to_db(app_context)
        assert app_context.settings.get("web.jwt_secret_key") == initial_token


class TestMigratePluginConfigToDb:
    def test_migrate_plugin_config_to_db_success(
        self, tmp_path, mock_db_session, app_context
    ):
        plugin_name = "test_plugin"
        plugin_config_data = {"enabled": True, "version": "1.0.0"}
        plugins_data = {plugin_name: plugin_config_data}
        plugin_config_path = tmp_path / "plugins.json"
        backup_config_path = tmp_path / "plugins.json.bak"
        with open(plugin_config_path, "w") as f:
            json.dump(plugins_data, f)

        migrate_plugin_config_to_db(app_context, str(tmp_path))

        mock_db_session.add.assert_called_once()
        added_plugin = mock_db_session.add.call_args[0][0]
        assert added_plugin.plugin_name == plugin_name
        assert added_plugin.config == plugin_config_data
        mock_db_session.commit.assert_called_once()
        assert backup_config_path.exists()

    def test_migrate_plugin_config_to_db_no_file(self, tmp_path, app_context):
        migrate_plugin_config_to_db(app_context, str(tmp_path))
        assert app_context.db.session_manager.call_count == 0


class TestMigrateServerConfigToDb:
    def test_migrate_server_config_to_db_success(
        self, tmp_path, mock_db_session, app_context
    ):
        server_name = "test_server"
        server_config_data = {"server_info": {"installed_version": "1.0.0"}}
        server_dir = tmp_path / server_name
        os.makedirs(server_dir)
        server_config_path = server_dir / f"{server_name}_config.json"
        backup_config_path = server_dir / f"{server_name}_config.json.bak"
        with open(server_config_path, "w") as f:
            json.dump(server_config_data, f)

        migrate_server_config_to_db(app_context, server_name, str(tmp_path))

        mock_db_session.add.assert_called_once()
        added_server = mock_db_session.add.call_args[0][0]
        assert added_server.server_name == server_name
        assert added_server.config == server_config_data
        mock_db_session.commit.assert_called_once()
        assert backup_config_path.exists()

    def test_migrate_server_config_to_db_no_file(self, tmp_path, app_context):
        migrate_server_config_to_db(app_context, "non_existent_server", str(tmp_path))
        assert app_context.db.session_manager.call_count == 0


class TestMigrateServicesToDb:
    @patch("platform.system", return_value="Linux")
    def test_migrate_services_to_db_success(self, mock_system, app_context, tmp_path):
        app_context.settings.set("paths.servers", str(tmp_path))

        server_dir = tmp_path / "test_server"
        os.makedirs(server_dir)

        server = app_context.get_server("test_server")
        with (
            patch.object(server, "is_installed", return_value=True),
            patch.object(server, "set_autostart") as mock_set_autostart,
        ):
            service_name = f"bedrock-{server.server_name}.service"
            service_path = os.path.join(
                os.path.expanduser("~"), ".config", "systemd", "user", service_name
            )
            os.makedirs(os.path.dirname(service_path), exist_ok=True)
            with open(service_path, "w") as f:
                f.write(
                    "[Unit]\nDescription=Test Service\n\n[Service]\nExecStart=/bin/true\n"
                )

            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "enabled"
                migrate_services_to_db(app_context=app_context)

            mock_set_autostart.assert_called_once_with(True)

            os.remove(service_path)

    @patch("platform.system", return_value="Windows")
    def test_migrate_windows_services_to_db_no_admin(
        self, mock_system, app_context, tmp_path
    ):
        app_context.settings.set("paths.servers", str(tmp_path))

        server_dir = tmp_path / "test_server"
        os.makedirs(server_dir)

        server = app_context.get_server("test_server")
        with (
            patch.object(server, "is_installed", return_value=True),
            patch.object(server, "set_autostart") as mock_set_autostart,
        ):
            with patch(
                "bedrock_server_manager.core.system.windows.check_service_exists",
                side_effect=Exception("Admin required"),
            ):
                migrate_services_to_db(app_context=app_context)

            mock_set_autostart.assert_not_called()


class TestMigrateEnvVarsToConfigFile:
    @patch("bedrock_server_manager.utils.migration.bcm_config.save_config")
    @patch("bedrock_server_manager.utils.migration.bcm_config.load_config")
    def test_migrate_env_vars_to_config_file_success(
        self, mock_load_config, mock_save_config, monkeypatch
    ):
        mock_load_config.return_value = {}
        monkeypatch.setenv("BEDROCK_SERVER_MANAGER_DATA_DIR", "/test/data/dir")

        migrate_env_vars_to_config_file()

        mock_save_config.assert_called_once_with({"data_dir": "/test/data/dir"})


class TestMigrateJsonSettingsToDb:
    def test_migrate_json_settings_to_db_success(
        self, app_context, tmp_path, mock_db_session
    ):
        config_data = {
            "config_version": 2,
            "web": {"port": 8080, "theme": "light"},
            "logging": {"cli_level": "DEBUG"},
            "custom": {"key1": "value1"},
        }
        config_path = tmp_path / "bedrock_server_manager.json"
        backup_path = tmp_path / "bedrock_server_manager.json.bak"
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        # Simulate existing settings in the DB that should be merged/overwritten
        existing_web_setting = Setting(
            key="web", value={"port": 11325, "host": "127.0.0.1"}
        )
        existing_logging_setting = Setting(key="logging", value={"file_level": "INFO"})

        def filter_by_side_effect(key):
            if key == "web":
                return MagicMock(first=MagicMock(return_value=existing_web_setting))
            elif key == "logging":
                return MagicMock(first=MagicMock(return_value=existing_logging_setting))
            else:
                return MagicMock(first=MagicMock(return_value=None))

        mock_db_session.query.return_value.filter_by.side_effect = filter_by_side_effect

        # Simulate that all settings are queried at the beginning
        mock_db_session.query.return_value.all.return_value = [
            existing_web_setting,
            existing_logging_setting,
        ]

        migrate_json_settings_to_db(app_context)

        # It should update 'web' and 'logging', and add 'config_version' and 'custom'
        assert mock_db_session.add.call_count == 2

        # Verify the deep merge logic
        assert existing_web_setting.value["port"] == 8080  # Overwritten
        assert existing_web_setting.value["theme"] == "light"  # Added
        assert existing_web_setting.value["host"] == "127.0.0.1"  # Preserved

        mock_db_session.commit.assert_called_once()
        assert app_context.settings.reload.called
        assert backup_path.exists()

    def test_migrate_json_settings_to_db_no_file(self, app_context):
        app_context.settings.config_dir = "non_existent_dir"
        migrate_json_settings_to_db(app_context)
        assert app_context.db.session_manager.call_count == 0


class TestLoadEnvFromSystemService:
    @patch("platform.system", return_value="Linux")
    def test_load_env_from_systemd_service_success(self, mock_system, tmp_path):
        from bedrock_server_manager.utils.migration import (
            _load_env_from_systemd_service,
        )

        service_name = "test.service"
        env_file_content = "BEDROCK_SERVER_MANAGER_USERNAME=testuser\nBEDROCK_SERVER_MANAGER_PASSWORD=testpassword"
        env_file_path = tmp_path / "test.env"
        with open(env_file_path, "w") as f:
            f.write(env_file_content)

        service_file_content = f"[Service]\nEnvironmentFile={env_file_path}"
        service_file_dir = tmp_path / ".config" / "systemd" / "user"
        os.makedirs(service_file_dir, exist_ok=True)
        service_file_path = service_file_dir / service_name
        with open(service_file_path, "w") as f:
            f.write(service_file_content)

        with patch(
            "bedrock_server_manager.core.system.linux.get_systemd_service_file_path",
            return_value=str(service_file_path),
        ):
            env_vars = _load_env_from_systemd_service(service_name)

        assert env_vars["BEDROCK_SERVER_MANAGER_USERNAME"] == "testuser"
        assert env_vars["BEDROCK_SERVER_MANAGER_PASSWORD"] == "testpassword"

    @patch("platform.system", return_value="Windows")
    def test_load_env_from_systemd_service_not_linux(self, mock_system):
        from bedrock_server_manager.utils.migration import (
            _load_env_from_systemd_service,
        )

        env_vars = _load_env_from_systemd_service("test.service")
        assert env_vars == {}

    @patch("platform.system", return_value="Linux")
    @patch(
        "bedrock_server_manager.core.system.linux.get_systemd_service_file_path",
        return_value="/path/to/non_existent_service_file",
    )
    def test_load_env_from_systemd_service_no_service_file(
        self, mock_get_path, mock_system
    ):
        from bedrock_server_manager.utils.migration import (
            _load_env_from_systemd_service,
        )

        env_vars = _load_env_from_systemd_service("test.service")
        assert env_vars == {}

    @patch(
        "bedrock_server_manager.utils.migration._load_env_from_systemd_service",
        return_value={},
    )
    @patch.dict(
        os.environ,
        {
            "BEDROCK_SERVER_MANAGER_USERNAME": "os_user",
            "BEDROCK_SERVER_MANAGER_PASSWORD": "os_password",
        },
        clear=True,
    )
    def test_migrate_env_auth_to_db_fallback_to_os_environ(
        self, mock_load_env, mock_db_session, app_context
    ):
        migrate_env_auth_to_db(app_context)
        mock_db_session.add.assert_called_once()
        added_user = mock_db_session.add.call_args[0][0]
        assert added_user.username == "os_user"
        mock_db_session.commit.assert_called_once()
