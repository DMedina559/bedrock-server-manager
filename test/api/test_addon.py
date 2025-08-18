import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.api.addon import import_addon
from bedrock_server_manager.error import AppFileNotFoundError, MissingArgumentError


class TestImportAddon:
    @patch(
        "bedrock_server_manager.core.server.addon_mixin.ServerAddonMixin.process_addon_file"
    )
    def test_import_addon_success_with_stop_start(
        self, mock_process_addon, app_context, tmp_path
    ):
        addon_file = tmp_path / "test.mcpack"
        addon_file.write_text("dummy content")
        server = app_context.get_server("test_server")

        result = import_addon("test_server", str(addon_file), app_context=app_context)
        assert result["status"] == "success"
        assert "installed successfully" in result["message"]
        mock_process_addon.assert_called_once_with(str(addon_file))

    @patch(
        "bedrock_server_manager.core.server.addon_mixin.ServerAddonMixin.process_addon_file"
    )
    def test_import_addon_success_no_stop_start(
        self, mock_process_addon, app_context, tmp_path
    ):
        addon_file = tmp_path / "test.mcpack"
        addon_file.write_text("dummy content")
        server = app_context.get_server("test_server")

        result = import_addon(
            "test_server",
            str(addon_file),
            stop_start_server=False,
            app_context=app_context,
        )
        assert result["status"] == "success"
        mock_process_addon.assert_called_once_with(str(addon_file))

    def test_import_addon_file_not_found(self, app_context):
        with pytest.raises(AppFileNotFoundError):
            import_addon(
                "test-server", "/non/existent/file.mcpack", app_context=app_context
            )

    def test_import_addon_no_server_name(self, app_context):
        with pytest.raises(MissingArgumentError):
            import_addon("", "file.mcpack", app_context=app_context)

    def test_import_addon_no_file_path(self, app_context):
        with pytest.raises(MissingArgumentError):
            import_addon("test-server", "", app_context=app_context)

    def test_import_addon_lock_skipped(self, tmp_path, app_context):
        addon_file = tmp_path / "test.mcpack"
        addon_file.write_text("dummy content")
        with patch("bedrock_server_manager.api.addon._addon_lock") as mock_lock:
            mock_lock.acquire.return_value = False
            result = import_addon(
                "test-server", str(addon_file), app_context=app_context
            )
            assert result["status"] == "skipped"

    @patch("bedrock_server_manager.api.addon.server_lifecycle_manager")
    def test_import_addon_exception(
        self, mock_lifecycle_manager, app_context, tmp_path
    ):
        addon_file = tmp_path / "test.mcpack"
        addon_file.write_text("dummy content")
        server = app_context.get_server("test_server")
        with patch.object(
            server,
            "process_addon_file",
            side_effect=Exception("Test exception"),
        ):
            result = import_addon(
                "test_server", str(addon_file), app_context=app_context
            )
            assert result["status"] == "error"
            assert "Test exception" in result["message"]
