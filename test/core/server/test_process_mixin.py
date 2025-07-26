import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.core.server.process_mixin import ServerProcessMixin
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.error import (
    ServerStartError,
    ServerNotRunningError,
    MissingArgumentError,
)


# Create a concrete class for testing that includes the mixin and necessary attributes/methods
class MockBedrockServer(ServerProcessMixin, BedrockServerBaseMixin):
    def __init__(
        self, server_name="test_server", base_dir="/servers", app_config_dir="/config"
    ):
        # Mock the base mixin's __init__
        self.server_name = server_name
        self.base_dir = base_dir
        self.app_config_dir = app_config_dir
        self.server_dir = f"{base_dir}/{server_name}"
        self.logger = MagicMock()
        self.settings = MagicMock()
        self.os_type = "Linux"
        self._resource_monitor = MagicMock()
        self.process_manager = MagicMock()

        # Mock methods from other mixins that are used by ServerProcessMixin
        self.is_installed = MagicMock(return_value=True)
        self.set_status_in_config = MagicMock()
        self.get_status_from_config = MagicMock(return_value="STOPPED")
        self.get_pid_file_path = MagicMock(
            return_value=f"{app_config_dir}/{server_name}/bedrock_{server_name}.pid"
        )


@pytest.fixture
def mock_server():
    """Fixture for a mocked BedrockServer instance."""
    return MockBedrockServer()


class TestServerProcessMixin:
    def test_is_running(self, mock_server):
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_server.process_manager.get_server_process.return_value = mock_process
        assert mock_server.is_running() is True
        mock_server.process_manager.get_server_process.assert_called_once_with(
            mock_server.server_name
        )

    def test_send_command(self, mock_server):
        with patch.object(mock_server, "is_running", return_value=True):
            mock_server.send_command("say hello")
            mock_server.process_manager.send_command.assert_called_once_with(
                mock_server.server_name, "say hello"
            )

    def test_send_command_not_running(self, mock_server):
        with patch.object(mock_server, "is_running", return_value=False):
            with pytest.raises(ServerNotRunningError):
                mock_server.send_command("say hello")

    def test_start(self, mock_server):
        """Tests the start method."""
        with patch.object(mock_server, "is_running", return_value=False):
            mock_server.start()
            mock_server.process_manager.start_server.assert_called_once_with(
                mock_server.server_name
            )
            mock_server.set_status_in_config.assert_any_call("STARTING")
            mock_server.set_status_in_config.assert_any_call("RUNNING")

    def test_start_already_running(self, mock_server):
        with patch.object(mock_server, "is_running", return_value=True):
            with pytest.raises(ServerStartError):
                mock_server.start()

    def test_stop(self, mock_server):
        with patch.object(mock_server, "is_running", return_value=True):
            mock_server.stop()
            mock_server.process_manager.stop_server.assert_called_once_with(
                mock_server.server_name
            )

    @patch("bedrock_server_manager.core.system.process.get_verified_bedrock_process")
    def test_get_process_info(self, mock_get_verified_process, mock_server):
        mock_process = MagicMock()
        mock_get_verified_process.return_value = mock_process
        mock_server._resource_monitor.get_stats.return_value = {"cpu": 50}

        info = mock_server.get_process_info()
        assert info == {"cpu": 50}
        mock_get_verified_process.assert_called_once_with(
            mock_server.server_name, mock_server.server_dir, mock_server.app_config_dir
        )
        mock_server._resource_monitor.get_stats.assert_called_once_with(mock_process)
