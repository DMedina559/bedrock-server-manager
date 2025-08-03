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


@pytest.fixture
def mock_get_server_instance(mocker, mock_bedrock_server):
    """Fixture to patch get_server_instance for the api.server module."""
    return mocker.patch(
        "bedrock_server_manager.api.server.get_server_instance",
        return_value=mock_bedrock_server,
    )


class TestServerSettings:
    def test_get_server_setting(self, real_bedrock_server):
        from bedrock_server_manager.db.models import Server
        from bedrock_server_manager.db.database import db_session_manager

        with patch(
            "bedrock_server_manager.api.server.get_server_instance",
            return_value=real_bedrock_server,
        ):
            # First, set a value so we have something to get
            set_server_setting("test-server", "custom.some_key", "some_value")

            result = get_server_setting("test-server", "custom.some_key")
            assert result["status"] == "success"
            assert result["value"] == "some_value"

    def test_set_server_setting(self, real_bedrock_server):
        from bedrock_server_manager.db.models import Server
        from bedrock_server_manager.db.database import db_session_manager

        with patch(
            "bedrock_server_manager.api.server.get_server_instance",
            return_value=real_bedrock_server,
        ):
            result = set_server_setting("test-server", "custom.some_key", "new_value")
            assert result["status"] == "success"

            with db_session_manager() as db_session:
                server = (
                    db_session.query(Server).filter_by(server_name="test_server").one()
                )
                config = server.config
                assert config["custom"]["some_key"] == "new_value"

    def test_set_server_custom_value(self, real_bedrock_server):
        from bedrock_server_manager.db.models import Server
        from bedrock_server_manager.db.database import db_session_manager

        with patch(
            "bedrock_server_manager.api.server.get_server_instance",
            return_value=real_bedrock_server,
        ):
            result = set_server_custom_value("test-server", "some_key", "custom_value")
            assert result["status"] == "success"

            with db_session_manager() as db_session:
                server = (
                    db_session.query(Server).filter_by(server_name="test_server").one()
                )
                config = server.config
                assert config["custom"]["some_key"] == "custom_value"

    def test_get_all_server_settings(self, real_bedrock_server):
        with patch(
            "bedrock_server_manager.api.server.get_server_instance",
            return_value=real_bedrock_server,
        ):
            result = get_all_server_settings("test-server")
            assert result["status"] == "success"

            # Check some of the default values
            assert result["data"]["server_info"]["installed_version"] == "UNKNOWN"
            assert result["data"]["settings"]["autoupdate"] is False


class TestServerLifecycle:
    def test_start_server(self, real_bedrock_server):
        with patch(
            "bedrock_server_manager.core.bedrock_process_manager.BedrockProcessManager.start_server"
        ) as mock_start:
            with patch(
                "bedrock_server_manager.api.server.get_server_instance",
                return_value=real_bedrock_server,
            ):
                result = start_server("test-server")
                assert result["status"] == "success"
                mock_start.assert_called_once_with(real_bedrock_server.server_name)

    def test_start_server_already_running(self, real_bedrock_server):
        with patch.object(real_bedrock_server, "is_running", return_value=True):
            with patch(
                "bedrock_server_manager.api.server.get_server_instance",
                return_value=real_bedrock_server,
            ):
                result = start_server("test-server")
                assert result["status"] == "error"
                assert "already running" in result["message"]

    def test_stop_server(self, real_bedrock_server):
        with patch(
            "bedrock_server_manager.core.bedrock_process_manager.BedrockProcessManager.stop_server"
        ) as mock_stop:
            with patch.object(real_bedrock_server, "is_running", return_value=True):
                with patch(
                    "bedrock_server_manager.api.server.get_server_instance",
                    return_value=real_bedrock_server,
                ):
                    result = stop_server("test-server")
                    assert result["status"] == "success"
                    mock_stop.assert_called_once_with(real_bedrock_server.server_name)

    def test_stop_server_already_stopped(self, real_bedrock_server):
        with patch.object(real_bedrock_server, "is_running", return_value=False):
            with patch(
                "bedrock_server_manager.api.server.get_server_instance",
                return_value=real_bedrock_server,
            ):
                result = stop_server("test-server")
                assert result["status"] == "error"
                assert "already stopped" in result["message"]

    @patch("bedrock_server_manager.api.server.stop_server")
    @patch("bedrock_server_manager.api.server.start_server")
    def test_restart_server(self, mock_start, mock_stop, real_bedrock_server):
        with patch(
            "bedrock_server_manager.api.server.get_server_instance",
            return_value=real_bedrock_server,
        ):
            with patch.object(real_bedrock_server, "is_running", return_value=True):
                mock_stop.return_value = {"status": "success"}
                mock_start.return_value = {"status": "success"}

                result = restart_server("test-server")
                assert result["status"] == "success"
                mock_stop.assert_called_once_with("test-server")
                mock_start.assert_called_once_with("test-server")


class TestSendCommand:
    def test_send_command(self, real_bedrock_server):
        with patch(
            "bedrock_server_manager.core.bedrock_process_manager.BedrockProcessManager.send_command"
        ) as mock_send:
            with patch.object(real_bedrock_server, "is_running", return_value=True):
                with patch(
                    "bedrock_server_manager.api.server.get_server_instance",
                    return_value=real_bedrock_server,
                ):
                    result = send_command("test-server", "say hello")
                    assert result["status"] == "success"
                    mock_send.assert_called_once_with(
                        real_bedrock_server.server_name, "say hello"
                    )

    def test_send_blocked_command(self, real_bedrock_server):
        with patch("bedrock_server_manager.api.server.API_COMMAND_BLACKLIST", ["stop"]):
            with pytest.raises(BlockedCommandError):
                send_command("test-server", "stop")

    def test_send_command_not_running(self, real_bedrock_server):
        with patch.object(real_bedrock_server, "is_running", return_value=False):
            with patch(
                "bedrock_server_manager.api.server.get_server_instance",
                return_value=real_bedrock_server,
            ):
                with pytest.raises(ServerNotRunningError):
                    send_command("test-server", "say hello")


class TestDeleteServer:
    def test_delete_server_data(self, mock_get_server_instance, mock_bedrock_server):
        result = delete_server_data("test-server")
        assert result["status"] == "success"
        mock_bedrock_server.delete_all_data.assert_called_once()

    @patch("bedrock_server_manager.api.server.stop_server")
    def test_delete_server_data_running(
        self, mock_stop, mock_get_server_instance, mock_bedrock_server
    ):
        mock_bedrock_server.is_running.return_value = True
        mock_stop.return_value = {"status": "success"}
        result = delete_server_data("test-server", stop_if_running=True)
        assert result["status"] == "success"
        mock_stop.assert_called_once_with("test-server")
        mock_bedrock_server.delete_all_data.assert_called_once()
