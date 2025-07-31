import pytest
from unittest.mock import patch, MagicMock
import os
import json
import importlib

from bedrock_server_manager.utils.migration import (
    migrate_players_json_to_db,
    migrate_env_auth_to_db,
    migrate_server_config_v1_to_v2,
    migrate_settings_v1_to_v2,
    migrate_env_token_to_db,
    migrate_plugin_config_to_db,
    migrate_server_config_to_db,
    migrate_services_to_db,
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
def mock_session_local(mock_db_session, mocker):
    """Fixture to patch db_session_manager."""
    mock_session_manager = mocker.MagicMock()
    mock_session_manager.return_value.__enter__.return_value = mock_db_session
    with patch(
        "bedrock_server_manager.utils.migration.db_session_manager",
        mock_session_manager,
    ) as mock:
        yield mock


class TestMigratePlayersJsonToDb:
    def test_migrate_players_json_to_db_success(
        self, tmp_path, mock_session_local, mock_db_session
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

        migrate_players_json_to_db(str(players_json_path))

        assert mock_db_session.add.call_count == 2
        mock_db_session.commit.assert_called_once()
        assert backup_json_path.exists()

    def test_migrate_players_json_to_db_file_not_found(self, mock_session_local):
        migrate_players_json_to_db("non_existent_file.json")
        mock_session_local.assert_not_called()

    def test_migrate_players_json_to_db_invalid_json(
        self, tmp_path, mock_session_local
    ):
        players_json_path = tmp_path / "players.json"
        with open(players_json_path, "w") as f:
            f.write("{invalid_json}")

        migrate_players_json_to_db(str(players_json_path))
        mock_session_local.assert_not_called()

    def test_migrate_players_json_to_db_db_error(
        self, tmp_path, mock_session_local, mock_db_session
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

        migrate_players_json_to_db(str(players_json_path))

        assert mock_db_session.add.call_count == 2
        mock_db_session.rollback.assert_called_once()
        assert backup_json_path.exists()


@patch("bedrock_server_manager.web.auth_utils.JWT_SECRET_KEY", "test_secret")
@patch("bedrock_server_manager.web.auth_utils.JWT_SECRET_KEY", "test_secret")
class TestMigrateEnvAuthToDb:
    @patch.dict(
        os.environ,
        {"TEST_USERNAME": "testuser", "TEST_PASSWORD": "testpassword"},
    )
    def test_migrate_env_auth_to_db_success(self, mock_session_local, mock_db_session):
        migrate_env_auth_to_db("TEST")

        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    def test_migrate_env_auth_to_db_no_env_vars(self, mock_session_local):
        migrate_env_auth_to_db("TEST")
        mock_session_local.assert_not_called()

    @patch.dict(
        os.environ,
        {"TEST_USERNAME": "testuser", "TEST_PASSWORD": "testpassword"},
    )
    def test_migrate_env_auth_to_db_user_exists(
        self, mock_session_local, mock_db_session
    ):
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = (
            User()
        )

        migrate_env_auth_to_db("TEST")

        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_not_called()

    @patch.dict(
        os.environ,
        {"TEST_USERNAME": "testuser", "TEST_PASSWORD": "testpassword"},
    )
    def test_migrate_env_auth_to_db_db_error(self, mock_session_local, mock_db_session):
        mock_db_session.commit.side_effect = Exception("DB error")

        migrate_env_auth_to_db("TEST")

        mock_db_session.add.assert_called_once()
        mock_db_session.rollback.assert_called_once()

    @patch.dict(
        os.environ,
        {
            "TEST_USERNAME": "testuser_hashed",
            "TEST_PASSWORD": "$2b$12$CoDITwbHQm4rzcWNk6VbR.we8YuV4vf9zUmZ6gQvsIVwcz7BWTOAy",
        },
    )
    def test_migrate_env_auth_to_db_with_hashed_password(
        self, mock_session_local, mock_db_session
    ):
        migrate_env_auth_to_db("TEST")

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
    @patch("bedrock_server_manager.instances.get_settings_instance")
    @patch.dict(os.environ, {"TEST_TOKEN": "test_token"})
    def test_migrate_env_token_to_db_success(self, mock_get_settings_instance):
        mock_settings = MagicMock()
        mock_get_settings_instance.return_value = mock_settings

        migrate_env_token_to_db("TEST")

        mock_settings.set.assert_called_once_with("web.jwt_secret_key", "test_token")

    @patch("bedrock_server_manager.instances.get_settings_instance")
    @patch.dict(os.environ, {}, clear=True)
    def test_migrate_env_token_to_db_no_token(self, mock_get_settings_instance):
        mock_settings = MagicMock()
        mock_get_settings_instance.return_value = mock_settings

        migrate_env_token_to_db("TEST")

        mock_settings.set.assert_not_called()


class TestMigratePluginConfigToDb:
    def test_migrate_plugin_config_to_db_success(
        self, tmp_path, mock_session_local, mock_db_session
    ):
        plugin_name = "test_plugin"
        plugin_config_data = {"enabled": True, "version": "1.0.0"}
        plugin_config_path = tmp_path / f"{plugin_name}.json"
        backup_config_path = tmp_path / f"{plugin_name}.json.bak"
        with open(plugin_config_path, "w") as f:
            json.dump(plugin_config_data, f)

        migrate_plugin_config_to_db(plugin_name, str(tmp_path))

        mock_db_session.add.assert_called_once()
        added_plugin = mock_db_session.add.call_args[0][0]
        assert added_plugin.plugin_name == plugin_name
        assert added_plugin.config == plugin_config_data
        mock_db_session.commit.assert_called_once()
        assert backup_config_path.exists()

    def test_migrate_plugin_config_to_db_no_file(
        self, tmp_path, mock_session_local, mock_db_session
    ):
        migrate_plugin_config_to_db("non_existent_plugin", str(tmp_path))
        mock_session_local.assert_not_called()


class TestMigrateServerConfigToDb:
    def test_migrate_server_config_to_db_success(
        self, tmp_path, mock_session_local, mock_db_session
    ):
        server_name = "test_server"
        server_config_data = {"server_info": {"installed_version": "1.0.0"}}
        server_config_path = tmp_path / f"{server_name}_config.json"
        backup_config_path = tmp_path / f"{server_name}_config.json.bak"
        with open(server_config_path, "w") as f:
            json.dump(server_config_data, f)

        migrate_server_config_to_db(server_name, str(tmp_path))

        mock_db_session.add.assert_called_once()
        added_server = mock_db_session.add.call_args[0][0]
        assert added_server.server_name == server_name
        assert added_server.config == server_config_data
        mock_db_session.commit.assert_called_once()
        assert backup_config_path.exists()

    def test_migrate_server_config_to_db_no_file(
        self, tmp_path, mock_session_local, mock_db_session
    ):
        migrate_server_config_to_db("non_existent_server", str(tmp_path))
        mock_session_local.assert_not_called()


class TestMigrateServicesToDb:
    @patch("platform.system", return_value="Linux")
    @patch("bedrock_server_manager.instances.get_settings_instance")
    @patch("bedrock_server_manager.instances.get_server_instance")
    def test_migrate_services_to_db_success(
        self,
        mock_get_server_instance,
        mock_get_settings_instance,
        mock_system,
        tmp_path,
    ):
        mock_settings = MagicMock()
        mock_settings.get.return_value = str(tmp_path)
        mock_get_settings_instance.return_value = mock_settings

        server_dir = tmp_path / "test_server"
        os.makedirs(server_dir)

        mock_server = MagicMock()
        mock_server.server_name = "test_server"
        mock_server.is_installed.return_value = True
        mock_get_server_instance.return_value = mock_server

        service_name = f"bedrock-{mock_server.server_name}.service"
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
            migrate_services_to_db()

        mock_server.set_autostart.assert_called_once_with(True)

        os.remove(service_path)

    @patch("platform.system", return_value="Windows")
    @patch("bedrock_server_manager.instances.get_settings_instance")
    @patch("bedrock_server_manager.instances.get_server_instance")
    def test_migrate_windows_services_to_db_no_admin(
        self,
        mock_get_server_instance,
        mock_get_settings_instance,
        mock_system,
        tmp_path,
    ):
        mock_settings = MagicMock()
        mock_settings.get.return_value = str(tmp_path)
        mock_get_settings_instance.return_value = mock_settings

        server_dir = tmp_path / "test_server"
        os.makedirs(server_dir)

        mock_server = MagicMock()
        mock_server.server_name = "test_server"
        mock_server.is_installed.return_value = True
        mock_get_server_instance.return_value = mock_server

        with patch(
            "bedrock_server_manager.core.system.windows.check_service_exists",
            side_effect=Exception("Admin required"),
        ):
            migrate_services_to_db()

        mock_server.set_autostart.assert_not_called()
