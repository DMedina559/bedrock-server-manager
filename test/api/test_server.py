import pytest
import os
import json
from unittest.mock import patch, MagicMock, ANY

from bedrock_server_manager.api.server import (
    get_server_setting,
    set_server_setting,
    set_server_custom_value,
    get_all_server_settings,
    start_server,
    stop_server,
    restart_server,
    send_command,
    delete_server_data,
)
from bedrock_server_manager.error import (
    BlockedCommandError,
    ServerNotRunningError,
)


class TestServerSettings:
    def test_get_server_setting(self, app_context):
        from bedrock_server_manager.db.models import Server
        from bedrock_server_manager.db.database import db_session_manager

        # First, set a value so we have something to get
        set_server_setting(
            "test_server", "custom.some_key", "some_value", app_context=app_context
        )

        result = get_server_setting(
            "test_server", "custom.some_key", app_context=app_context
        )
        assert result["status"] == "success"
        assert result["value"] == "some_value"

    def test_set_server_setting(self, app_context):
        from bedrock_server_manager.db.models import Server
        from bedrock_server_manager.db.database import db_session_manager

        result = set_server_setting(
            "test_server", "custom.some_key", "new_value", app_context=app_context
        )
        assert result["status"] == "success"

        with db_session_manager() as db_session:
            server = db_session.query(Server).filter_by(server_name="test_server").one()
            config = server.config
            assert config["custom"]["some_key"] == "new_value"

    def test_set_server_custom_value(self, app_context):
        from bedrock_server_manager.db.models import Server
        from bedrock_server_manager.db.database import db_session_manager

        result = set_server_custom_value(
            "test_server", "some_key", "custom_value", app_context=app_context
        )
        assert result["status"] == "success"

        with db_session_manager() as db_session:
            server = db_session.query(Server).filter_by(server_name="test_server").one()
            config = server.config
            assert config["custom"]["some_key"] == "custom_value"

    def test_get_all_server_settings(self, app_context):
        result = get_all_server_settings("test_server", app_context=app_context)
        assert result["status"] == "success"

        # Check some of the default values
        assert result["data"]["server_info"]["installed_version"] == "UNKNOWN"
        assert result["data"]["settings"]["autoupdate"] is False


class TestServerLifecycle:
    def test_start_server(self, app_context):
        server = app_context.get_server("test_server")
        with patch.object(server.process_manager, "start_server") as mock_start:
            result = start_server("test_server", app_context=app_context)
            assert result["status"] == "success"
            mock_start.assert_called_once_with(server.server_name)

    def test_start_server_already_running(self, app_context):
        server = app_context.get_server("test_server")
        with patch.object(server, "is_running", return_value=True):
            result = start_server("test_server", app_context=app_context)
            assert result["status"] == "error"
            assert "already running" in result["message"]

    def test_stop_server(self, app_context):
        server = app_context.get_server("test_server")
        with patch.object(server.process_manager, "stop_server") as mock_stop:
            with patch.object(server, "is_running", return_value=True):
                result = stop_server("test_server", app_context=app_context)
                assert result["status"] == "success"
                mock_stop.assert_called_once_with(server.server_name)

    def test_stop_server_already_stopped(self, app_context):
        server = app_context.get_server("test_server")
        with patch.object(server, "is_running", return_value=False):
            result = stop_server("test_server", app_context=app_context)
            assert result["status"] == "error"
            assert "already stopped" in result["message"]

    @patch("bedrock_server_manager.api.server.stop_server")
    @patch("bedrock_server_manager.api.server.start_server")
    def test_restart_server(self, mock_start, mock_stop, app_context):
        server = app_context.get_server("test_server")
        with patch.object(server, "is_running", return_value=True):
            mock_stop.return_value = {"status": "success"}
            mock_start.return_value = {"status": "success"}

            result = restart_server("test_server", app_context=app_context)
            assert result["status"] == "success"
            mock_stop.assert_called_once()
            assert mock_stop.call_args[0][0] == "test_server"
            mock_start.assert_called_once()
            assert mock_start.call_args[0][0] == "test_server"


class TestSendCommand:
    def test_send_command(self, app_context):
        server = app_context.get_server("test_server")
        with patch.object(server.process_manager, "send_command") as mock_send:
            with patch.object(server, "is_running", return_value=True):
                result = send_command(
                    "test_server", "say hello", app_context=app_context
                )
                assert result["status"] == "success"
                mock_send.assert_called_once_with(server.server_name, "say hello")

    def test_send_blocked_command(self, app_context):
        with patch("bedrock_server_manager.api.server.API_COMMAND_BLACKLIST", ["stop"]):
            with pytest.raises(BlockedCommandError):
                send_command("test_server", "stop", app_context=app_context)

    def test_send_command_not_running(self, app_context):
        server = app_context.get_server("test_server")
        with patch.object(server, "is_running", return_value=False):
            with pytest.raises(ServerNotRunningError):
                send_command("test_server", "say hello", app_context=app_context)


class TestDeleteServer:
    def test_delete_server_data(self, app_context):
        server = app_context.get_server("test_server")
        server_dir = server.server_dir
        config_dir = server.server_config_dir
        backup_dir = server.server_backup_directory

        # Ensure directories exist before deletion
        os.makedirs(server_dir, exist_ok=True)
        os.makedirs(config_dir, exist_ok=True)
        os.makedirs(backup_dir, exist_ok=True)

        result = delete_server_data("test_server", app_context=app_context)
        assert result["status"] == "success"

        # Verify that directories are deleted
        assert not os.path.exists(server_dir)
        assert not os.path.exists(config_dir)
        assert not os.path.exists(backup_dir)

    def test_delete_server_data_running(self, app_context):
        server = app_context.get_server("test_server")
        server_dir = server.server_dir
        config_dir = server.server_config_dir
        backup_dir = server.server_backup_directory

        # Ensure directories exist before deletion
        os.makedirs(server_dir, exist_ok=True)
        os.makedirs(config_dir, exist_ok=True)
        os.makedirs(backup_dir, exist_ok=True)

        with (
            patch.object(server, "is_running", return_value=True),
            patch.object(server, "stop") as mock_server_stop,
        ):
            result = delete_server_data(
                "test_server", stop_if_running=True, app_context=app_context
            )
            assert result["status"] == "success"
            assert mock_server_stop.call_count >= 1

        # Verify that directories are deleted
        assert not os.path.exists(server_dir)
        assert not os.path.exists(config_dir)
        assert not os.path.exists(backup_dir)
