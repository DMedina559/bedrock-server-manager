import pytest
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
def mock_bedrock_server(tmp_path):
    """Fixture for a mocked BedrockServer."""
    server = MagicMock()
    server.server_name = "test-server"
    server.server_config_dir = str(tmp_path)
    server.is_running.return_value = False
    server.check_service_exists.return_value = False
    server.is_service_active.return_value = False
    return server


@pytest.fixture
def mock_get_server_instance(mock_bedrock_server):
    """Fixture to patch get_server_instance."""
    with patch(
        "bedrock_server_manager.api.server.get_server_instance",
        return_value=mock_bedrock_server,
    ) as mock:
        yield mock


class TestServerSettings:
    def test_get_server_setting(self, mock_get_server_instance, mock_bedrock_server):
        mock_bedrock_server._manage_json_config.return_value = "test_value"
        result = get_server_setting("test-server", "some.key")
        assert result["status"] == "success"
        assert result["value"] == "test_value"
        mock_bedrock_server._manage_json_config.assert_called_once_with(
            "some.key", "read"
        )

    def test_set_server_setting(self, mock_get_server_instance, mock_bedrock_server):
        result = set_server_setting("test-server", "some.key", "new_value")
        assert result["status"] == "success"
        mock_bedrock_server._manage_json_config.assert_called_once_with(
            "some.key", "write", "new_value"
        )

    def test_set_server_custom_value(
        self, mock_get_server_instance, mock_bedrock_server
    ):
        result = set_server_custom_value("test-server", "custom_key", "custom_value")
        assert result["status"] == "success"
        mock_bedrock_server.set_custom_config_value.assert_called_once_with(
            "custom_key", "custom_value"
        )

    def test_get_all_server_settings(
        self, mock_get_server_instance, mock_bedrock_server
    ):
        mock_bedrock_server._load_server_config.return_value = {"all": "settings"}
        result = get_all_server_settings("test-server")
        assert result["status"] == "success"
        assert result["data"] == {"all": "settings"}
        mock_bedrock_server._load_server_config.assert_called_once()


class TestServerLifecycle:
    def test_start_server_direct(self, mock_get_server_instance, mock_bedrock_server):
        result = start_server("test-server", mode="direct")
        assert result["status"] == "success"
        mock_bedrock_server.start.assert_called_once()

    @patch("bedrock_server_manager.api.server.launch_detached_process")
    def test_start_server_detached(
        self, mock_launch, mock_get_server_instance, mock_bedrock_server
    ):
        mock_launch.return_value = 12345
        result = start_server("test-server", mode="detached")
        assert result["status"] == "success"
        assert result["pid"] == 12345
        mock_launch.assert_called_once()

    def test_start_server_already_running(
        self, mock_get_server_instance, mock_bedrock_server
    ):
        mock_bedrock_server.is_running.return_value = True
        result = start_server("test-server")
        assert result["status"] == "error"
        assert "already running" in result["message"]

    def test_stop_server(self, mock_get_server_instance, mock_bedrock_server):
        mock_bedrock_server.is_running.return_value = True
        result = stop_server("test-server")
        assert result["status"] == "success"
        mock_bedrock_server.stop.assert_called_once()

    def test_stop_server_already_stopped(
        self, mock_get_server_instance, mock_bedrock_server
    ):
        result = stop_server("test-server")
        assert result["status"] == "error"
        assert "already stopped" in result["message"]

    @patch("bedrock_server_manager.api.server.stop_server")
    @patch("bedrock_server_manager.api.server.start_server")
    def test_restart_server(
        self, mock_start, mock_stop, mock_get_server_instance, mock_bedrock_server
    ):
        mock_bedrock_server.is_running.return_value = True
        mock_stop.return_value = {"status": "success"}
        mock_start.return_value = {"status": "success"}

        result = restart_server("test-server")
        assert result["status"] == "success"
        mock_stop.assert_called_once_with("test-server")
        mock_start.assert_called_once_with("test-server", mode="detached")


class TestSendCommand:
    def test_send_command(self, mock_get_server_instance, mock_bedrock_server):
        mock_bedrock_server.is_running.return_value = True
        result = send_command("test-server", "say hello")
        assert result["status"] == "success"
        mock_bedrock_server.send_command.assert_called_once_with("say hello")

    def test_send_blocked_command(self, mock_get_server_instance, mock_bedrock_server):
        with patch("bedrock_server_manager.api.server.API_COMMAND_BLACKLIST", ["stop"]):
            with pytest.raises(BlockedCommandError):
                send_command("test-server", "stop")

    def test_send_command_not_running(
        self, mock_get_server_instance, mock_bedrock_server
    ):
        mock_bedrock_server.send_command.side_effect = ServerNotRunningError
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
