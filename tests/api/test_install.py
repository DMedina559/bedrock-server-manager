from unittest.mock import patch

from bedrock_server_manager.api.install import (
    install_new_server,
    update_server,
)


class TestInstallUpdate:
    @patch("bedrock_server_manager.utils.server.core_validate_server_name_format")
    @patch("os.path.exists", return_value=False)
    def test_install_new_server(self, mock_exists, mock_validate, app_context):
        mock_validate.return_value = None
        server = app_context.get_server("new-server")
        with patch.object(server, "install_or_update") as mock_install:
            result = install_new_server("new-server", app_context=app_context)
            assert result["status"] == "success"
            mock_install.assert_called_once()

    @patch("bedrock_server_manager.api.install.server_lifecycle_manager")
    def test_update_server(self, mock_lifecycle, app_context):
        server = app_context.get_server("test_server")
        with patch.object(server, "is_update_needed", return_value=True):
            with patch.object(server, "backup_all_data") as mock_backup:
                with patch.object(server, "install_or_update") as mock_install:
                    result = update_server("test_server", app_context=app_context)
                    assert result["status"] == "success"
                    assert result["updated"] is True
                    mock_lifecycle.assert_called_once()
                    mock_backup.assert_called_once()
                    mock_install.assert_called_once()
