import pytest
from unittest.mock import patch, MagicMock
import os
import json

from bedrock_server_manager.utils.migration import (
    migrate_players_json_to_db,
    migrate_env_auth_to_db,
    migrate_server_config_v1_to_v2,
    migrate_settings_v1_to_v2,
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
        with open(players_json_path, "w") as f:
            json.dump(players_data, f)

        migrate_players_json_to_db(str(players_json_path))

        assert mock_db_session.add.call_count == 2
        mock_db_session.commit.assert_called_once()

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
        with open(players_json_path, "w") as f:
            json.dump(players_data, f)

        mock_db_session.commit.side_effect = Exception("DB error")

        migrate_players_json_to_db(str(players_json_path))

        assert mock_db_session.add.call_count == 2
        mock_db_session.rollback.assert_called_once()


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
